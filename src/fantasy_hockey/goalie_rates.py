"""Separate starter/relief scoring from permitted, normalized historical inputs."""
from collections import defaultdict
from datetime import date
from math import isfinite


def estimate_rates(history: dict, boxes: list[dict], weights: dict, as_of: date,
                   prior_starts: float = 20) -> dict:
    """Exclude flagged conflicts; shrink observed means toward the same-role cohort.

The fixed prior strength is an experimental assumption. Missing individual
samples stay missing. No relief exposure is silently added to a start forecast.
"""
    if not isfinite(prior_starts) or prior_starts < 0:raise ValueError('Invalid prior strength')
    conflicts={(str(r['game_id']),str(r['id'])) for r in history.get('source_conflicts',[])}
    records={}; groups=defaultdict(list); seen=set(); excluded=defaultdict(int)
    for r in history['records']:
        if r['kind']!='goalie':continue
        key=(str(r['game_id']),str(r['id']))
        if key in records:raise ValueError('Duplicate normalized goalie record')
        records[key]=r
    for box in boxes:
        game=str(box['game_id']);pid=str(box['player_id'])
        if game[4:6]!='02':continue
        key=(game,pid)
        if key in seen:raise ValueError('Duplicate starter classification')
        seen.add(key)
        if key not in records:raise ValueError('Starter classification missing normalized record')
        r=records[key]
        if date.fromisoformat(r['date'])>as_of:raise ValueError('Future goalie outcome')
        if key in conflicts:excluded[pid]+=1;continue
        if not r['appeared']:continue
        status=str(box['starter']).lower()
        if status not in {'true','false'}:raise ValueError('Unknown starter status')
        points=sum(float(r['stats'][k])*float(v) for k,v in weights.items())
        if not isfinite(points):raise ValueError('Nonfinite goalie points')
        groups[(pid,'start' if status=='true' else 'relief')].append(points)
    missing=[key for key,r in records.items() if r['appeared'] and key not in seen and key not in conflicts]
    if missing:raise ValueError('Appeared goalie has no starter classification')
    cohort={role:[v for (pid,kind),values in groups.items() if kind==role for v in values] for role in ('start','relief')}
    result={}
    for pid in sorted({pid for _,pid in records}):
        out={'excluded_conflicts':excluded[pid]}
        for role in ('start','relief'):
            values=groups[pid,role];others=[v for (other,kind),samples in groups.items() if kind==role and other!=pid for v in samples]
            anchor=sum(others)/len(others) if others else None
            mean=sum(values)/len(values) if values else None
            shrunk=(sum(values)+prior_starts*anchor)/(len(values)+prior_starts) if values and anchor is not None else mean
            out[role]={'sample':len(values),'mean_points':mean,'shrunk_points':shrunk,'cohort_points':anchor,
                       'small_sample':len(values)<20}
        result['nhl:'+pid]=out
    return {'season':history['season'],'as_of':as_of.isoformat(),'prior_strength':prior_starts,
            'players':result,'warnings':['Conflict-flagged games excluded; missing samples remain missing',
            'Fixed shrinkage strength is unvalidated; start and relief cohorts are separate',
            'Only previous regular-season outcomes; team and role changes can alter rates']}
