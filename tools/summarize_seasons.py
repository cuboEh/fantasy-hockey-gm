"""Summarize chronological policy comparisons; never promote a model."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--studies',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    grouped=defaultdict(list);seen=set()
    for directory in a.studies:
        for path in directory.glob('season-*.json'):
            report=json.loads(path.read_text());year=report['ending_year']
            if report.get('market_matched_players',0):raise ValueError('Keep market sensitivity separate from synthetic-opponent seeds')
            for run in report['runs']:
                key=(year,run['model_name'],run['teams'],run['seat'],run['seed'])
                if key in seen:raise ValueError('Duplicate experiment scenario')
                seen.add(key)
                if run['active']:
                    assert all(w['adds']<=report.get('transaction_assumptions',{}).get('max_acquisitions',4) for w in run['active']['weeks'].values())
                    opponent_ids={p['id'] for p in run['picks'] if p['team']!=run['seat']}
                    assert all(t['add'] not in opponent_ids for t in run['active']['transactions'])
                grouped[year].append(run)
    models=sorted({r['model_name'] for runs in grouped.values() for r in runs})
    baseline='shrink0_workload0_points_fixed';past=defaultdict(list);year_rows=[]
    for year,runs in sorted(grouped.items()):
        # Select using earlier seasons only. This does not undo researcher's
        # prior inspection or make an already-developed policy a pristine test.
        selected=max(models,key=lambda m:(mean(past[m]) if past[m] else (0 if m==baseline else -float('inf'))))
        means={m:mean(r['paired_penalty_scenario_delta'] for r in runs if r['model_name']==m) for m in models}
        stream=mean(r['active']['zero_goalie_penalty_scenario']-r['fixed']['zero_goalie_penalty_scenario'] for r in runs if r['active'])
        year_rows.append({'ending_year':year,'policy_deltas':means,'streaming_delta':stream,'selected_from_earlier_years':selected,'selected_delta':means[selected]})
        for m in models:past[m].append(means[m])
    summary={m:{'mean_delta':mean(row['policy_deltas'][m] for row in year_rows),
                'positive_years':sum(row['policy_deltas'][m]>0 for row in year_rows),
                'ordinary_season_mean':mean(row['policy_deltas'][m] for row in year_rows if row['ending_year'] not in {2020,2021})} for m in models}
    result={'years':year_rows,'summary':summary,'draft_scenarios':len(seen),
            'streaming_mean':mean(row['streaming_delta'] for row in year_rows),
            'walk_forward_selection_mean':mean(row['selected_delta'] for row in year_rows),
            'warnings':['Reconstructed historical data with provider conflicts; not verified official fantasy outcomes',
                        'Policies were designed during research; walk-forward accounting is not a pristine holdout',
                        'No confidence intervals from correlated draft seats/seeds; no automatic model promotion']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2))
    lines=['# Multi-season research results','', 'Mean differences use goalie-minimum-adjusted lineup points, not bench production. These are research simulations, not forecasts of actual league performance.','',
           '| Season | Cohort workload | Replacement | Usable-game draft | Streaming, same baseline draft |','| --- | ---: | ---: | ---: | ---: |']
    for r in year_rows:
        v=r['policy_deltas'];y=r['ending_year']
        lines.append(f"| {y-1}-{str(y)[-2:]} | {v['shrink20_workload0.5_points_cohort']:.1f} | {v['shrink0_workload0_replacement_fixed']:.1f} | {v['shrink0_workload0_usable_fixed']:.1f} | {r['streaming_delta']:.1f} |")
    lines+=['','Four fixed-roster draft policies, two synthetic opponent seeds, three draft seats in each of 12/13-team leagues. Streaming is evaluated separately from the same baseline draft.','',
            'All target seasons are reconstructed from prior-season universes. Rookie coverage, pre-draft injuries, original schedule publication dates, actual Yahoo eligibility, opponent streaming and waiver competition remain limitations. Source disagreements are flagged.','',
            'No policy has been promoted to the live draft board. See docs/six-step-implementation.md for sources, rules and reproduction commands.']
    a.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:result[k] for k in ('summary','draft_scenarios','streaming_mean','walk_forward_selection_mean')},indent=2))


if __name__=='__main__':main()
