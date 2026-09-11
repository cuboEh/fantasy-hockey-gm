"""Walk-forward evaluation of fixed historical-analogue adjustments."""
import argparse
from pathlib import Path
import json
import hashlib
from statistics import mean
from research.analogues import summarize,candidates,examples,predict
from fantasy_hockey.board import dump_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.md').exists():p.error('Preserve earlier runs; choose a new output')
    annual={};hashes={};conflicts={}
    for year in range(2013,2027):
        path=a.history_dir/f'history-{year}.json';data=json.loads(path.read_text())
        if data['season']!=f'{year-1}{year}':raise ValueError('Season mismatch')
        annual[year]=summarize(data);hashes[year]=hashlib.sha256(path.read_bytes()).hexdigest();conflicts[year]=len(data['source_conflicts'])
    history=examples(annual);runs=[]
    for year in range(2018,2027):
        cases=[r for r in history if r['target']==year]
        training=[r for r in history if r['target']<year]
        top_ids={r['id'] for r in sorted(cases,key=lambda r:(-r['baseline_points'],r['id']))[:224]}
        for group in ('F','D','G'):
            errors=[];draft_errors=[]
            for case in cases:
                if case['group']!=group:continue
                pred=predict(case,training)
                errors.append({'baseline':abs(case['baseline_points']-case['actual_points']),
                               'workload':abs(pred['workload_points']-case['actual_points']),
                               'workload_rate':abs(pred['points']-case['actual_points']),
                               'baseline_gp':abs(case['baseline_games']-case['actual_games']),
                               'adjusted_gp':abs(pred['games']-case['actual_games'])})
                if case['id'] in top_ids:draft_errors.append(errors[-1])
            runs.append({'year':year,'group':group,'players':len(errors),
                         'mae':{k:mean(r[k] for r in errors) for k in errors[0]},
                         'draft_relevant_players':len(draft_errors),
                         'draft_relevant_mae':{k:mean(r[k] for r in draft_errors) for k in errors[0]} if draft_errors else None})
        print(year,'complete',flush=True)
    summary={group:{k:mean(r['mae'][k] for r in runs if r['group']==group) for k in runs[0]['mae']} for group in ('F','D','G')}
    draft_summary={group:{k:mean(r['draft_relevant_mae'][k] for r in runs if r['group']==group and r['draft_relevant_mae']) for k in runs[0]['mae']} for group in ('F','D','G')}
    ids={'8480801','8477493','8482093','8482661','8479406'}
    current=[{'candidate':c,'estimate':predict(c,history)} for c in candidates(annual,2027) if c['id'] in ids]
    result={'evaluation':runs,'mean_season_mae':summary,'draft_relevant_mae':draft_summary,'current_analogues':current,'history_sha256':hashes,
            'source_conflicts':conflicts,'settings':{'k':40,'shrink_prior':40,'minimum_neighbors':10},
            'warnings':['Training outcomes strictly precede each predicted season; query player excluded from training neighbors',
                        'Fixed settings, not tuned to these test outcomes; research already inspected, not a pristine holdout',
                        'No dated surgery severity, return clearance or upcoming offseason role labels in historical data',
                        'Past in-season team changes are observed proxies, not causal effects of an upcoming trade',
                        'Missing players assigned zero NHL production assuming complete season coverage, including retirement/departure',
                        'All results use 82-game equivalents based on last observed team schedule; current numbers are not 84-game live-board forecasts',
                        'Repeated players and seasons are correlated; errors not confidence intervals',
                        'Rates evaluated only with adequate-returning-neighbor samples; rookies without NHL history absent',
                        'Whole-player points, not usable lineup points; no automatic model promotion']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(dump_json(result))
    lines=['# Historical analogue evaluation','',*result['warnings'],'',
           'Nine target seasons: 2017-18 through 2025-26. Mean season-level absolute point error, lower is better.','',
           '| Group | Historical baseline | Workload correction | Workload + rate |','| --- | ---: | ---: | ---: |']
    for group,row in summary.items():lines.append(f"| {group} | {row['baseline']:.1f} | {row['workload']:.1f} | {row['workload_rate']:.1f} |")
    lines+=['','## Draft-relevant subset','', 'Top 224 by pre-season baseline points, chosen before observing outcomes. This ignores position demand.','',
            '| Group | Historical baseline | Workload correction | Workload + rate |','| --- | ---: | ---: | ---: |']
    for group,row in draft_summary.items():lines.append(f"| {group} | {row['baseline']:.1f} | {row['workload']:.1f} | {row['workload_rate']:.1f} |")
    lines+=['','## Current player analogues','', 'These estimates do not incorporate current injury or deployment evidence.']
    for row in current:
        c=row['candidate'];pred=row['estimate']
        lines+=['',f"### {c['name']} ({c['id']})",f"Historical baseline {c['baseline_points']:.1f}; analogue estimate {pred['points']:.1f} points on an 82-game basis.",
                'Nearest historical examples: '+', '.join(f"{n['name']} entering {n['target']-1}-{str(n['target'])[-2:]}" for n in pred['neighbors'][:5])]
    a.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(dump_json({'all_players':summary,'draft_relevant':draft_summary}))


if __name__=='__main__':main()
