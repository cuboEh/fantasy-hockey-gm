"""Frozen chronological diagnostic: historical roles only, never current news.

Outcomes are consumed only after picks are locked. These seasons have previously
been explored, so this is not an untouched holdout or prospective accuracy claim.
"""
import argparse
from collections import defaultdict
import csv
from datetime import date
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from fantasy_hockey.backtest import Model, forecast
from fantasy_hockey.config import load_config
from fantasy_hockey.seasonlab import prepare_history, replay_season
from fantasy_hockey.goalie_coverage import coverage_evaluator
from fantasy_hockey.goalie_rates import estimate_rates
from fantasy_hockey.draft_value import DraftPlayer, Exposure, RosterValue
from fantasy_hockey.draft_planner import preferences, shortlist, fits, compare_turns
from fantasy_hockey.draft import snake_team
from fantasy_hockey.draft_completion import complete_draft, continuation_utility

POLICIES=('points_frozen','coverage_frozen','scenario_greedy','scenario_two_turn')


def historical_players(base,metadata,previous,rates):
    games=previous['team_games'];raw={};totals=defaultdict(float)
    ranks={p.id:i for i,p in enumerate(sorted(base,key=lambda p:(-p.points,p.id)),1)}
    for p in base:
        if p.kind=='goalie':
            item=rates['players'].get('nhl:'+p.id,{})
            n=item.get('start',{}).get('sample',0);relief=item.get('relief',{}).get('sample',0)
            fraction=n/(n+relief) if n+relief else 0
            raw[p.id]=p.games/82*fraction
            totals[metadata[p.id]['team']]+=raw[p.id]
    current=[];opponents=[]
    for p in base:
        team=metadata[p.id]['team'];opportunities=games.get(team)
        old=Exposure(p.games/82*(opportunities or mean(games.values())),p.rate)
        opponents.append(DraftPlayer(p.id,p.name,team,p.kind,(p.position,),old,old,ranks[p.id]))
        if opportunities is None:
            exp=None
        elif p.kind=='goalie':
            rate=rates['players'].get('nhl:'+p.id,{}).get('start',{}).get('shrunk_points')
            exp=Exposure(raw[p.id]/max(1,totals[team])*opportunities,rate) if rate is not None else None
        else:exp=old
        current.append(DraftPlayer(p.id,p.name,team,p.kind,(p.position,),exp,exp,ranks[p.id]))
    return current,opponents


def play(policy,players,opponents,slots,seat,seed,style,value,legacy,base):
    mapping={p.id:p for p in players};order=preferences(opponents,seed,style)
    # Keep opponents' exact order while referring to the own-model identity objects.
    order=[mapping[p.id] for p in order]
    rosters=defaultdict(list);taken=set();picks=[];seconds=0
    base_order=sorted(base,key=lambda p:(-p.points,p.id))
    scenario_utility=continuation_utility(players,value) if policy=='starter_coverage' else None
    for n in range(1,14*sum(v for p,v in slots.items() if p not in {'IR','IR+'})+1):
        team=snake_team(n,14)
        if team!=seat:
            chosen=next(p for p in order if p.id not in taken and fits(p,rosters[team],mapping,slots))
        else:
            start=perf_counter()
            if policy=='scenario_completion':
                # Planning uncertainty is independent of realized opponent preferences.
                planning={10001:[mapping[p.id] for p in preferences(opponents,10001,style)]}
                advice=complete_draft(players,picks,slots,14,seat,value,(10001,),style,
                                      width=4,opponent_orders=planning)
                chosen=mapping[advice['choice']]
            elif policy=='starter_coverage':
                candidates=shortlist([p for p in players if p.id not in taken],rosters[team],mapping,slots,width=4)
                chosen=max(candidates,key=lambda p:(scenario_utility(p,rosters[team]),p.id))
            elif policy=='scenario_two_turn':
                advice=compare_turns(players,picks,slots,14,seat,value,(seed,),style,width=4,opponent_orders={seed:order})
                chosen=mapping[advice['baseline_choice']]
            elif policy=='scenario_greedy':
                candidates=shortlist([p for p in players if p.id not in taken],rosters[team],mapping,slots,width=4)
                chosen=max(candidates,key=lambda p:(value.evaluate(rosters[team]+[p.id])['points'],p.id))
            else:
                candidates=[p for p in base_order if p.id not in taken and fits(mapping[p.id],rosters[team],mapping,slots)]
                best=max(candidates[:12],key=lambda p:(legacy(p,rosters[team]),p.points,p.id)) if policy=='coverage_frozen' else candidates[0]
                chosen=mapping[best.id]
            seconds+=perf_counter()-start
        taken.add(chosen.id);rosters[team].append(chosen.id)
        picks.append({'pick':n,'team':team,'id':chosen.id,'name':chosen.name})
    return picks,seconds


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--years',type=int,nargs='+',default=list(range(2015,2027)))
    p.add_argument('--styles',nargs='+',default=['rank','points','goalie_early'])
    p.add_argument('--seats',type=int,nargs='+',default=[1,7,14])
    p.add_argument('--policies',nargs='+',choices=POLICIES+('starter_coverage','scenario_completion'),default=POLICIES)
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new output directory')
    policies=tuple(a.policies)
    if 'scenario_completion' in policies and a.seed==10001:
        p.error('Realized opponent seed must differ from completion planning seed 10001')
    if len(set(policies))!=len(policies):p.error('Policies must be distinct')
    config=load_config(Path('config.local.toml'));slots=dict(config.slots)
    source_paths=list(Path('src/fantasy_hockey').glob('*.py'))+[Path(__file__)]
    manifest={'policies':policies,'years':a.years,'seats':a.seats,'styles':a.styles,'seed':a.seed,'completion_planning_seed':10001,
              'prior_strength':20,'shortlist_width':4,'lineups':'same baseline forecasts for every replay',
              'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
              'warning':'Previously explored seasons; locked diagnostic specification, not untouched validation. No current role news in history.'}
    inputs=[Path('config.local.toml')] + [Path(f'var/history-{y}.json') for y in range(2013,max(a.years)+1)] + [Path(f'snapshots/2026-09-10/sportsdataverse/goalie_box_{y-1}.csv') for y in a.years]
    manifest['input_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    a.output_dir.mkdir(parents=True);(a.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2))
    all_rows=[]
    for year in a.years:
        seasons={y:json.loads(Path(f'var/history-{y}.json').read_text()) for y in range(max(2013,year-3),year+1)}
        metadata,history=prepare_history(seasons,year);base=forecast(history,Model())
        with Path(f'snapshots/2026-09-10/sportsdataverse/goalie_box_{year-1}.csv').open() as f:boxes=list(csv.DictReader(f))
        rate=estimate_rates(seasons[year-1],boxes,config.weights['goalie'],date(year-1,9,13))
        players,opponents=historical_players(base,metadata,seasons[year-1],rate)
        value=RosterValue(players,seasons[year-1],slots)
        legacy=coverage_evaluator(base,metadata,seasons[year-1],slots)
        forecasts={p.id:p for p in base};records=defaultdict(list)
        for r in seasons[year]['records']:records[r['id']].append(r)
        runs=[]
        for style in a.styles:
            for seat in a.seats:
                for policy in policies:
                    picks,seconds=play(policy,players,opponents,slots,seat,a.seed,style,value,legacy,base)
                    ids=[r['id'] for r in picks if r['team']==seat]
                    season={**seasons[year],'records':[r for pid in ids for r in records[pid]]}
                    outcome=replay_season(season,picks,forecasts,metadata,slots,seat)
                    row={'year':year,'style':style,'seat':seat,'policy':policy,'decision_seconds':seconds,
                         'counted_points':outcome['zero_goalie_penalty_scenario'],
                         'failed_weeks':outcome['goalie_minimum_failed_weeks'],
                         'goalies_drafted':sum(forecasts[pid].kind=='goalie' for pid in ids)}
                    runs.append({**row,'picks':picks,'weeks':outcome['weeks']});all_rows.append(row)
                group=runs[-len(policies):]
                common=set.intersection(*({w for w,v in r['weeks'].items() if not v['source_conflicts']} for r in group))
                for full,flat in zip(group,all_rows[-len(policies):]):
                    metrics={'common_clean_weeks':len(common),
                             'common_clean_points':sum(full['weeks'][w]['zero_goalie_penalty_scenario'] for w in common),
                             'common_clean_failed_weeks':sum(not full['weeks'][w]['goalie_minimum_met'] for w in common)}
                    full.update(metrics);flat.update(metrics)
                print('Completed',year,style,seat,flush=True)
        (a.output_dir/f'season-{year}.json').write_text(json.dumps({'runs':runs,'unsupported_prior_team_ids':[p.id for p in players if p.team not in seasons[year-1]['team_games']]},indent=2))
        (a.output_dir/'rows.json').write_text(json.dumps(all_rows,indent=2))
    summary={policy:{key:mean(r[key] for r in all_rows if r['policy']==policy) for key in ['counted_points','failed_weeks','goalies_drafted','decision_seconds','common_clean_points','common_clean_failed_weeks']} for policy in policies}
    (a.output_dir/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
