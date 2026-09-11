"""Frozen chronological diagnostic: historical roles only, never current news.

Outcomes are consumed only after picks are locked. These seasons have previously
been explored, so this is not an untouched holdout or prospective accuracy claim.
"""
import argparse
from collections import defaultdict
import csv
from datetime import date
from dataclasses import asdict, replace
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
                planning={10001:[mapping[p.id] for p in preferences(opponents,10001,style)]}
                advice=compare_turns(players,picks,slots,14,seat,value,(10001,),style,width=4,opponent_orders=planning)
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
    p.add_argument('--working-replay', action='store_true', help='Freeze a bounded 2024-25 opportunity diagnostic before opening outcomes')
    p.add_argument('--years',type=int,nargs='+',default=list(range(2015,2027)))
    p.add_argument('--styles',nargs='+',default=['rank','points','goalie_early'])
    p.add_argument('--seats',type=int,nargs='+',default=[1,7,14])
    p.add_argument('--policies',nargs='+',choices=POLICIES+('starter_coverage','scenario_completion'),default=POLICIES)
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new output directory')
    if a.working_replay:
        working_replay(a.output_dir,a.seats,a.seed)
        return
    policies=tuple(a.policies)
    if set(policies)&{'scenario_completion','scenario_two_turn'} and a.seed==10001:
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



def error_components(projected_games, projected_rate, observed_games, observed_points):
    """Exact signed FP decomposition, including zero observed appearances.

    Missing source observations must be flagged separately by the caller.
    """
    return {
        'workload_error_points': (observed_games-projected_games)*projected_rate,
        'rate_error_points': observed_points-observed_games*projected_rate,
        'total_error_points': observed_points-projected_games*projected_rate,
    }


def historical_opportunity_inputs(seasons, target, draft_date, weights):
    """Reject outcomes at the input boundary; rescore raw stats with our rules."""
    from fantasy_hockey.scoring import score
    if any(y >= target for y in seasons):
        raise ValueError('Target/future season cannot enter frozen draft inputs')
    cleaned={}
    for year,season in seasons.items():
        if any(date.fromisoformat(r['date']) >= draft_date for r in season['records']):
            raise ValueError('Historical record follows draft cutoff')
        cleaned[year]={**season,'records':[
            {**r,'points':float(score(r['kind'],r['stats'],weights[r['kind']]).total)}
            for r in season['records']]}
    metadata,history=prepare_history(cleaned,target)
    # A three-season rate history does not establish current NHL eligibility.
    # Conservative historical proxy, independent of any target-year appearance.
    history=[row for row in history if any(year==target-1 for year,_,_ in row[-1])]
    base=forecast(history,Model())
    metadata={p.id:metadata[p.id] for p in base}
    calendar=cleaned[target-1]
    players=[]
    for p in base:
        team=metadata[p.id]['team']
        exp=Exposure(p.games/82*calendar['team_games'][team],p.rate)
        players.append(DraftPlayer(p.id,p.name,team,p.kind,(p.position,),exp,exp))
    return metadata,base,players,calendar


def audit_replay(outcome, season):
    """Missing selected-player rows invalidate weeks, never silently verify zeros."""
    from fantasy_hockey.seasonlab import week_key
    observed={(r['date'],r['id']) for r in season['records']}
    missing=[{'date':d['date'],'id':pid} for d in outcome['daily_picks']
             for pid in d['selected'] if (d['date'],pid) not in observed]
    invalid={week_key(r['date']) for r in missing}
    invalid.update(w for w,r in outcome['weeks'].items() if r['source_conflicts'])
    return {'missing_selected_observations':missing,'invalid_weeks':sorted(invalid),
            'usable_weeks':sorted(set(outcome['weeks'])-invalid)}


def working_replay(output, seats, seed):
    """One fixed historical diagnostic, not validation of today's DtZ forecasts."""
    from fantasy_hockey.market import load_market
    from fantasy_hockey.scoring import score
    if seed in (10001,10002):raise ValueError('Realized opponent seed overlaps planning seeds')
    if not seats or len(set(seats))!=len(seats) or any(not 1<=s<=14 for s in seats):
        raise ValueError('Use unique seats between 1 and 14')
    config=load_config(Path('config.local.toml'));slots=dict(config.slots)
    cutoff=date(2024,9,26);target=2025
    prior_paths=[Path(f'var/history-{y}.json') for y in (2022,2023,2024)]
    market_path=Path('private/market-2024.csv')
    metadata,base,players,calendar=historical_opportunity_inputs(
        {y:json.loads(path.read_text()) for y,path in zip((2022,2023,2024),prior_paths)},target,cutoff,config.weights)
    market=load_market(market_path,'20242025',cutoff)
    players=[replace(p,market_rank=market[p.id]['value'] if p.id in market else None) for p in players]
    mapping={p.id:p for p in players}
    realized=preferences(players,seed,'rank')
    orders={s:preferences(players,s,'rank') for s in (10001,10002)}
    policies=('points','market_proxy','two_pick')
    manifest={
        'target_ending_year':target,'draft_date':str(cutoff),'seats':seats,'policies':policies,
        'actual_opponent_seed':seed,'planning_seeds':list(orders),
        'model':asdict(Model()),'shortlist_width':4,'market_matched':len(set(market)&set(mapping)),
        'warnings':[
            'Reconstructed diagnostic on previously explored history, not an untouched holdout.',
            'Historical ADP workbook retrieved in 2026 is mutable; not verified archived Yahoo data.',
            'Missing ADP follows all supplied ADP, then projected points. Rookies without prior NHL history are absent.',
            'Prior primary positions and last observed teams, not archived Yahoo eligibility or offseason rosters.',
            'Require an appearance in the immediately prior NHL season. This excludes retired/departed stale records but also rookies and full-season absentees.',
            'Prior completed calendar is the draft opportunity proxy. Final target calendar is used only for daily replay.',
            'Frozen historical rate/GP baseline, not the current DtZ provider or a test of its accuracy.',
            'No injuries, confirmed starters, waiver activity or in-season projection updates enter lineup decisions.',
            'Monday-Sunday qualification and zero-goalie-points penalty are scenarios, not verified Yahoo matchup rules.',
            'Missing selected rows invalidate strict weekly comparisons. Provisional totals assume absent rows are zero.',
        ],
        'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in prior_paths+[market_path,Path('private/market-2024.metadata.json'),Path('snapshots/2026-09-10/csg-2024/receipt.json'),Path('config.local.toml')]},
        'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in list(Path('src/fantasy_hockey').glob('*.py'))+[Path(__file__)]},
    }
    output.mkdir(parents=True)
    (output/'specification.json').write_text(json.dumps(manifest,indent=2))
    runs=[]
    for seat in seats:
        for policy in policies:
            value=RosterValue(players,calendar,slots,draft_opportunity=True)
            picks=[];taken=set();rosters=defaultdict(list);decisions=[]
            for n in range(1,225):
                team=snake_team(n,14)
                if team!=seat:
                    chosen=next(p for p in realized if p.id not in taken and fits(p,rosters[team],mapping,slots))
                else:
                    legal=[p for p in players if p.id not in taken and fits(p,rosters[team],mapping,slots)]
                    raw=max(legal,key=lambda p:(p.baseline.games*p.baseline.rate,p.id))
                    market_best=min(legal,key=lambda p:(p.market_rank if p.market_rank is not None else 1e9,-p.baseline.games*p.baseline.rate,p.id))
                    if policy=='points':chosen=raw
                    elif policy=='market_proxy':chosen=market_best
                    else:
                        incremental=max(legal,key=lambda p:(value.evaluate(rosters[seat]+[p.id])['points'],p.id))
                        advice=compare_turns(players,picks,slots,14,seat,value,seeds=tuple(orders),width=4,
                            opponent_orders=orders,fixed_next_pick=True,include_ids=(raw.id,market_best.id,incremental.id))
                        chosen=mapping[advice['baseline_choice']]
                        decisions.append({'pick':n,'choice':chosen.id,'points_choice':raw.id,'candidates':advice['candidates']})
                taken.add(chosen.id);rosters[team].append(chosen.id)
                picks.append({'pick':n,'team':team,'id':chosen.id})
            runs.append({'seat':seat,'policy':policy,'picks':picks,'roster':rosters[seat],
                         'forecast_value':value.evaluate(rosters[seat]),'decisions':decisions})
            print('Frozen',seat,policy,flush=True)
    frozen={'specification':manifest,'forecasts':[asdict(p) for p in base],'metadata':metadata,'runs':runs}
    frozen_path=output/'frozen-drafts.json';frozen_path.write_text(json.dumps(frozen,indent=2))
    # This is the first opening of target outcomes. Every draft is already on disk.
    target_path=Path(f'var/history-{target}.json');season=json.loads(target_path.read_text())
    season={**season,'records':[{**r,'points':float(score(r['kind'],r['stats'],config.weights[r['kind']]).total)} for r in season['records']]}
    forecasts={p.id:p for p in base};by_player=defaultdict(list)
    for r in season['records']:by_player[r['id']].append(r)
    summaries=[]
    for run in runs:
        outcome=replay_season(season,run['picks'],forecasts,metadata,slots,run['seat'])
        audit=audit_replay(outcome,season);errors=[]
        for pid in run['roster']:
            p=forecasts[pid];records=[r for r in by_player[pid] if r['appeared']]
            gp=len(records);points=sum(r['points'] for r in records)
            errors.append({'id':pid,'name':p.name,'kind':p.kind,'projected_games':p.games,'projected_rate':p.rate,
                'observed_games':gp,'observed_points':points,'observed_rate':points/gp if gp else None,
                'no_observations':not bool(by_player[pid]),**error_components(p.games,p.rate,gp,points)})
        summary={'seat':run['seat'],'policy':run['policy'],'forecast_lineup_proxy':run['forecast_value']['points'],
            'provisional_counted_points':outcome['zero_goalie_penalty_scenario'],
            'provisional_bench_points':sum(w['bench'] for w in outcome['weeks'].values()),
            'provisional_goalie_forfeiture':outcome['lineup_points']-outcome['zero_goalie_penalty_scenario'],
            'provisional_failed_weeks':outcome['goalie_minimum_failed_weeks'],
            'goalies':sum(forecasts[pid].kind=='goalie' for pid in run['roster']),
            'missing_selected_observations':len(audit['missing_selected_observations']),
            'strict_usable_weeks':len(audit['usable_weeks']),
            'error_totals':{key:sum(e[key] for e in errors) for key in ('workload_error_points','rate_error_points','total_error_points')}}
        summaries.append(summary)
        (output/f"seat-{run['seat']}-{run['policy']}-outcome.json").write_text(json.dumps({'summary':summary,'errors':errors,'audit':audit,'replay':outcome},indent=2))
        run['outcome']=outcome;run['audit']=audit
    for seat in seats:
        group=[r for r in runs if r['seat']==seat]
        common=set.intersection(*(set(r['audit']['usable_weeks']) for r in group))
        for r in group:
            summary=next(s for s in summaries if s['seat']==seat and s['policy']==r['policy'])
            summary['common_complete_observation_weeks']=len(common)
            summary['common_complete_observation_points']=sum(r['outcome']['weeks'][w]['qualified_points'] for w in common) if common else None
    report={'specification':manifest,'rows':summaries,'frozen_drafts_sha256':hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
            'outcome_sha256':hashlib.sha256(target_path.read_bytes()).hexdigest(),
            'interpretation':'Provisional diagnostic only. Strict common weeks exclude missing outcomes and recorded conflicts; no competitive-advantage conclusion.'}
    (output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(summaries,indent=2),flush=True)




if __name__=='__main__':main()
