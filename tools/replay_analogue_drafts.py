"""Paired 14-team draft/replay experiment for frozen analogue corrections."""
import argparse
from collections import defaultdict
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from statistics import mean

from fantasy_hockey.analogues import summarize,candidates,examples,predict
from fantasy_hockey.backtest import Model,forecast,mock_draft
from fantasy_hockey.config import load_config
from fantasy_hockey.seasonlab import prepare_history,replay_season,opportunity_evaluator
from fantasy_hockey.board import dump_json
from tools.score_matchups import compare
from fantasy_hockey.goalie_coverage import coverage_evaluator


def corrected_pools(baseline, annual, target, training):
    candidate_map={r['id']:r for r in candidates(annual,target)}
    workload=[];full=[];details=[]
    for p in baseline:
        c=candidate_map[p.id];pred=predict(c,training)
        games=max(0,min(82,p.games+pred['games']-c['baseline_games']))
        rate=p.rate+pred['rate']-c['baseline_rate']
        workload.append(replace(p,games=games,points=p.rate*games))
        full.append(replace(p,games=games,rate=rate,points=rate*games))
        details.append({'id':p.id,'games':games,'rate':rate,'fallback':pred['fallback'],
                        'neighbors':pred['neighbors']})
    return workload,full,details


def paired_records(matches):
    """All variants must use the same source-conflict-free weeks."""
    common=set.intersection(*({r['week'] for r in m['weeks']} for m in matches))
    return [{'wins':sum(r['outcome']=='wins' for r in m['weeks'] if r['week'] in common),
             'ties':sum(r['outcome']=='ties' for r in m['weeks'] if r['week'] in common),
             'weeks':len(common)} for m in matches]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history-dir',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--years',type=int,nargs='+',default=list(range(2018,2027)))
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new experiment directory')
    config=load_config(a.config);slots=dict(config.slots)
    seasons={y:json.loads((a.history_dir/f'history-{y}.json').read_text()) for y in range(2013,max(a.years)+1)}
    annual={y:summarize(s) for y,s in seasons.items()};training=examples(annual,last=max(a.years))
    a.output_dir.mkdir(parents=True);all_rows=[]
    for year in a.years:
        players,history=prepare_history(seasons,year);base=forecast(history,Model())
        work,full,details=corrected_pools(base,annual,year,training)
        policies={'baseline_points':(base,'points'),'baseline_usable':(base,'usable'),
                  'analogue_workload':(work,'points'),'analogue_points':(full,'points'),'analogue_usable':(full,'usable'),
                  'baseline_coverage':(base,'coverage'),'analogue_coverage':(full,'coverage')}
        mappings={key:{p.id:p for p in pool} for key,(pool,_) in policies.items()}
        utilities={key:opportunity_evaluator(pool,players,seasons[year-1],slots) for key,(pool,strategy) in policies.items() if strategy=='usable'}
        utilities.update({key:coverage_evaluator(pool,players,seasons[year-1],slots)
                          for key,(pool,strategy) in policies.items() if strategy=='coverage'})
        records_by_id=defaultdict(list)
        for row in seasons[year]['records']:records_by_id[row['id']].append(row)
        cache={}
        def replay(picks,seat,model):
            ids=tuple(sorted(r['id'] for r in picks if r['team']==seat))
            key=(ids,model)
            if key not in cache:
                # Fixed roster only. Other players' outcomes cannot affect this team's decisions.
                season={**seasons[year],'records':[r for pid in ids for r in records_by_id[pid]]}
                result=replay_season(season,picks,mappings[model],players,slots,seat)
                cache[key]={k:v for k,v in result.items() if k not in {'daily_picks','transactions'}}
            return cache[key]
        runs=[]
        for seed in (0,1):
            for seat in (1,7,14):
                group=[];matches=[]
                for name,(pool,strategy) in policies.items():
                    picks=mock_draft(pool,base,slots,14,seat,seed,strategy,pick_value=utilities.get(name))
                    assert len(picks)==224 and len({r['id'] for r in picks})==224
                    fixed=replay(picks,seat,'baseline_points')
                    own=replay(picks,seat,name)
                    opponents={s:replay(picks,s,'baseline_points') for s in range(1,15) if s!=seat}
                    match_fixed=compare(fixed,opponents,seat,14);match_own=compare(own,opponents,seat,14)
                    matches.extend([match_fixed,match_own])
                    group.append({'year':year,'seed':seed,'seat':seat,'policy':name,'picks':picks,
                                  'fixed_lineups':fixed,'own_lineups':own})
                records=paired_records(matches)
                for i,r in enumerate(group):r.update(fixed_matchups=records[i*2],own_matchups=records[i*2+1])
                baseline=group[0]
                for r in group:
                    r['draft_only_delta']=r['fixed_lineups']['zero_goalie_penalty_scenario']-baseline['fixed_lineups']['zero_goalie_penalty_scenario']
                    r['total_delta']=r['own_lineups']['zero_goalie_penalty_scenario']-baseline['own_lineups']['zero_goalie_penalty_scenario']
                    r['lineup_effect']=r['total_delta']-r['draft_only_delta']
                    r['failed_goalie_weeks']=r['own_lineups']['goalie_minimum_failed_weeks']
                    r['goalies_drafted']=sum(mappings[r['policy']][p['id']].position=='G' for p in r['picks'] if p['team']==seat)
                    r['wins_delta']=r['own_matchups']['wins']-baseline['own_matchups']['wins']
                    runs.append(r)
        output={'year':year,'runs':runs,'forecast_details':details,
                'config_sha256':hashlib.sha256(a.config.read_bytes()).hexdigest(),
                'history_sha256':{str(y):hashlib.sha256((a.history_dir/f'history-{y}.json').read_bytes()).hexdigest() for y in range(2013,year+1)}}
        (a.output_dir/f'season-{year}.json').write_text(dump_json(output))
        for r in runs:all_rows.append({k:v for k,v in r.items() if k not in {'picks','fixed_lineups','own_lineups'}})
        print('Completed',year,flush=True)
    metrics=('draft_only_delta','total_delta','lineup_effect','wins_delta','failed_goalie_weeks','goalies_drafted')
    summary={name:{m:mean(r[m] for r in all_rows if r['policy']==name) for m in metrics} for name in policies}
    year_summary={year:{name:mean(r['total_delta'] for r in all_rows if r['year']==year and r['policy']==name) for name in policies} for year in a.years}
    report={'summary':summary,'year_summary':year_summary,'scenarios':len(all_rows),'rows':all_rows,
            'warnings':['Same seats and opponent ranking preferences; opponent rosters change naturally when our picks change',
                        'Draft-only comparison fixes all lineup forecasts to baseline; total comparison also changes our lineup forecasts',
                        'Opponents always use baseline lineup forecasts; no streaming or waiver competition',
                        'Synthetic round-robin H2H, not actual Yahoo matchups; common conflict-free weeks across all policies',
                        'Full-season point totals include flagged source conflicts; H2H excludes affected common weeks',
                        'Minimum three goalie appearances enforced; primary positions and reconstructed calendars remain limitations',
                        'No future training outcomes or own-player neighbors; historic data were already explored in research',
                        'No current news/rookie universe, no causal injury/trade model, no automatic live model promotion',
                        'Coverage credits reductions in expected forfeited points using independent prior-calendar start proxies; same-team starts mutually exclusive',
                        'All utility policies retain the same top-12 fitting candidate shortlist; coverage is a heuristic, not global optimization']}
    (a.output_dir/'summary.json').write_text(dump_json(report))
    lines=['# Analogue draft and season replay','',*report['warnings'],'',
           '| Policy | Draft-only FP change | Total FP change | Lineup effect | H2H win change | Failed goalie weeks | Goalies drafted |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,r in summary.items():lines.append(f"| {name} | {r['draft_only_delta']:+.1f} | {r['total_delta']:+.1f} | {r['lineup_effect']:+.1f} | {r['wins_delta']:+.2f} | {r['failed_goalie_weeks']:.2f} | {r['goalies_drafted']:.2f} |")
    (a.output_dir/'summary.md').write_text('\n'.join(lines)+'\n');print(dump_json(summary))


if __name__=='__main__':main()
