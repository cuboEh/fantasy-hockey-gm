"""Validate researched goalie scenarios without conflating review with certainty."""
from collections import Counter
from datetime import date
from math import isfinite, isclose


def validate_review(payload: dict, as_of: date) -> dict:
    """Version-two reviews reconcile every ID against joint team start budgets."""
    if payload.get('review_version') != 2:raise ValueError('Expected workload review version 2')
    if date.fromisoformat(payload['as_of']) > as_of:raise ValueError('Future workload review')
    rows=payload['goalies']; ids=[g['id'] for g in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate goalie review ID')
    if not payload.get('assumptions'):raise ValueError('Missing analyst assumptions')
    mapped={g['id']:g for g in rows}
    for g in rows:
        status=g['review_status']
        if status not in {'source_reviewed_scenario','reviewed_unresolved'}:raise ValueError('Unreviewed entry remains')
        e=g.get('evidence')
        if not e or not e.get('source') or not e.get('fact'):raise ValueError('Missing review evidence')
        if date.fromisoformat(e['date'])>as_of:raise ValueError('Future source evidence')
        date.fromisoformat(g['review_by'])
        values=[g['baseline_starts'],g['downside_starts']]
        if status=='reviewed_unresolved':
            if values != [None,None]:raise ValueError('Unresolved job must not be assigned starts')
        else:
            if any(v is None or not isfinite(float(v)) or not 0<=float(v)<=84 for v in values):raise ValueError('Invalid starts')
            if values[1]>values[0]:raise ValueError('Downside exceeds baseline')
            if g['rate'] is None or not isfinite(float(g['rate'])):raise ValueError('Missing rate')
    if set(payload['teams']) != {g['team'] for g in rows}:raise ValueError('Team ledger missing or unrelated')
    for team,ledger in payload['teams'].items():
        for case,key,reserve in [('baseline','starts','other_starts'),('downside','downside_starts','downside_other_starts')]:
            expected={g['id']:g[case+'_starts'] for g in rows if g['team']==team and g[case+'_starts'] is not None}
            if ledger[key]!=expected:raise ValueError('Team ledger and player IDs/starts disagree')
            remaining=float(ledger[reserve])
            if not isfinite(remaining) or remaining<0 or not isclose(sum(expected.values())+remaining,84,abs_tol=1e-8):raise ValueError('Team starts must total 84')
    reviewed=payload.get('newly_reviewed_ids',[])
    if len(reviewed)!=len(set(reviewed)) or set(reviewed)-mapped.keys():raise ValueError('Invalid reviewed ID list')
    return {'goalies':len(rows),'status_counts':dict(Counter(g['review_status'] for g in rows)),
            'teams':len(payload['teams']),'newly_reviewed':len(reviewed),
            'unresolved_ids':[g['id'] for g in rows if g['review_status']=='reviewed_unresolved']}
