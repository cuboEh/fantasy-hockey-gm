"""Offline schedule and workload scenario reports."""
from datetime import date
import hashlib
import json
from pathlib import Path
from .goalie_weeks import weekly_coverage


def register(commands):
    p=commands.add_parser('goalie-weeks',help='Compare goalie coverage using explicit workload scenarios')
    p.add_argument('--schedule',type=Path,required=True)
    p.add_argument('--workloads',type=Path,required=True)
    p.add_argument('--goalies',nargs='+',required=True,help='Internal player IDs')
    p.add_argument('--case',choices=['baseline','downside'],default='baseline')
    p.add_argument('--as-of',type=date.fromisoformat,default=date.today())
    p.add_argument('--json',action='store_true')


def report(schedule, workloads, ids, case, as_of):
    if workloads.get('review_version') == 2:
        from .workload_review import validate_review
        validate_review(workloads,as_of)
    if not ids:raise ValueError('Select at least one goalie')
    if case not in {'baseline','downside'}:raise ValueError('Unknown workload case')
    if workloads['season'].replace('-','') != str(schedule['season'])[:4]+str(schedule['season'])[-2:]:
        raise ValueError('Workload and schedule seasons differ')
    if date.fromisoformat(workloads['as_of'])>as_of:raise ValueError('Future workload evidence')
    mapping={g['id']:g for g in workloads['goalies']}
    chosen=[];warnings=list(workloads['assumptions'])
    for pid in ids:
        if pid not in mapping:raise ValueError(f'Unknown goalie: {pid}')
        g=mapping[pid]
        if g[case+'_starts'] is None or g['rate'] is None:raise ValueError(f'Missing workload/rate: {pid}')
        if g.get('evidence') and date.fromisoformat(g['evidence']['date'])>as_of:raise ValueError('Future source evidence')
        if date.fromisoformat(g['review_by'])<as_of:warnings.append(f"{g['name']}: review overdue")
        if g['review_status']!='source_reviewed_scenario':warnings.append(f"{g['name']}: role not source-reviewed")
        chosen.append({**g,'starts':g[case+'_starts']})
    weeks=weekly_coverage(schedule,chosen)
    warnings.extend(['Monday-Sunday calendar weeks are not verified Yahoo matchup periods; includes shortened opening/closing and break weeks.',
                     'Independent start proxy, not calibrated category or matchup win probabilities. Two daily goalie slots; no streaming or confirmed-start news.',
                     'Conditional points hold historical per-appearance rates fixed; no automatic board promotion.'])
    return {'case':case,'goalies':chosen,'weeks':weeks,'warnings':warnings,
            'summary':{'calendar_weeks':len(weeks),'expected_failed_weeks_proxy':sum(w['failure_probability_proxy'] for w in weeks),
                       'impossible_weeks':[w['week'] for w in weeks if w['minimum_impossible']],
                       'qualified_points_proxy':sum(w['qualified_points'] for w in weeks)},
            'schedule_source_kind':schedule['source_kind']}


def handle(args):
    schedule=json.loads(args.schedule.read_text());workloads=json.loads(args.workloads.read_text())
    result=report(schedule,workloads,args.goalies,args.case,args.as_of)
    result['input_sha256']={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in [('schedule',args.schedule),('workloads',args.workloads)]}
    if args.json:print(json.dumps(result,indent=2));return 0
    print(' / '.join(g['name'] for g in result['goalies'])+f' | {args.case} scenario')
    print('Week        Expected starts   Failure proxy   Collision days')
    for w in result['weeks']:
        print(f"{w['week']}  {w['expected_starts']:>15.2f}  {w['failure_probability_proxy']:>13.1%}  {w['collision_days']:>14}"+('  MINIMUM IMPOSSIBLE' if w['minimum_impossible'] else ''))
    for warning in result['warnings']:print('NOTE: '+warning)
    return 0
