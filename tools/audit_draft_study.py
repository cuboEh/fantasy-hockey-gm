"""Rescore frozen mock picks with explicit, sourced outcome corrections.

Never changes forecasts, selections, source history or the original report.
Run: uv run python tools/audit_draft_study.py STUDY CORRECTIONS OUTPUT
Corrections JSON: {"target":2025,"players":{"NHL_ID":{"points":0,
"games":0,"source":"URL","verified_at":"YYYY-MM-DD","reason":"..."}}}
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
from statistics import mean

from fantasy_hockey.scoring import number


def audit(study, corrections):
    if corrections.get('target') != study['evaluation_season']:
        raise ValueError('Correction season does not match evaluation')
    updates=corrections.get('players',{})
    for player_id,row in updates.items():
        if not row.get('source') or not row.get('reason'):
            raise ValueError('Correction requires source and reason')
        date.fromisoformat(row['verified_at'])
        gp=number(row['games'],'games'); points=number(row['points'],'points')
        if gp < 0 or gp > 90 or (gp == 0 and points != 0):
            raise ValueError('Invalid outcome games/points')
    runs=[]; contributions=Counter(); uses=Counter(); seen=set()
    for run in study['evaluation']['runs']:
        totals={}; missing={}; values={}
        for side in ('result','benchmark'):
            values[side]={};missing[side]=[]
            for pick in run[side]['pick_outcomes']:
                identity=pick['id'];value=pick['actual_points']
                if identity in updates:
                    value=float(number(updates[identity]['points'],'points'))
                    uses[side]+=1;seen.add(identity)
                if value is None:
                    missing[side].append(identity)
                else:
                    values[side][identity]=value
            totals[side]=None if missing[side] else sum(values[side].values())
        delta=None if any(v is None for v in totals.values()) else totals['result']-totals['benchmark']
        runs.append({'teams':run['teams'],'seat':run['seat'],'seed':run['seed'],
                     'totals':totals,'remaining_missing':missing,'paired_delta':delta})
        if delta is not None:
            for side,sign in [('result',1),('benchmark',-1)]:
                for identity,value in values[side].items():
                    contributions[identity]+=sign*value
    if set(updates)-seen:
        raise ValueError('Correction IDs were not present in evaluated rosters')
    deltas=[r['paired_delta'] for r in runs if r['paired_delta'] is not None]
    return {'purpose':'Post-draft outcome audit; no model retuning',
            'corrections':corrections,'corrected_roster_counts':dict(uses),'runs':runs,
            'complete_pairs':len(deltas),'mean_paired_delta':mean(deltas) if deltas else None,
            'positive_pairs':sum(d>0 for d in deltas),
            'min_delta':min(deltas) if deltas else None,'max_delta':max(deltas) if deltas else None,
            'mean_point_contributions':{p:v/len(deltas) for p,v in contributions.items()} if deltas else {},
            'warnings':study['warnings']+['Contributions reflect selection frequency, not causal player effects']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('study','corrections','output'):parser.add_argument(arg,type=Path)
    args=parser.parse_args()
    if args.output.resolve() in {args.study.resolve(),args.corrections.resolve()}:
        parser.error('Output cannot overwrite inputs')
    result=audit(json.loads(args.study.read_text()),json.loads(args.corrections.read_text()))
    result['study_sha256']=hashlib.sha256(args.study.read_bytes()).hexdigest()
    result['corrections_sha256']=hashlib.sha256(args.corrections.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('complete_pairs','mean_paired_delta','positive_pairs','min_delta','max_delta')},indent=2))


if __name__=='__main__':main()
