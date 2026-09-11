"""Read-only integration of the draft tracker, reviewed scenarios and two-turn search."""
from datetime import date
import hashlib
import json
from pathlib import Path

from .draft import connect, settings
from .draft_value import DraftPlayer, Exposure, RosterValue
from .draft_planner import compare_turns
from .workload_review import validate_review


def build_players(board,workloads,rates,as_of,context=None,case_map=None):
    validate_review(workloads,as_of)
    if workloads['season']!=board['season'] or date.fromisoformat(board['as_of'])>as_of:raise ValueError('Board/review date or season mismatch')
    start=int(board['season'][:4]);prior=f'{start-1}{start}'
    if board.get('config_sha256') and board['config_sha256'] not in rates.get('input_sha256',{}).values():raise ValueError('Starter-rate scoring configuration differs from board')
    if context and context.get('board_sha256') != workloads.get('board_sha256'):raise ValueError('Context and workload reviews refer to different boards')
    if rates['season']!=prior or date.fromisoformat(rates['as_of'])>as_of:raise ValueError('Starter rates must use the previous season and precede analysis')
    review={g['id']:g for g in workloads['goalies']}; result=[];notes={};overrides={}
    if bool(context)!=bool(case_map):raise ValueError('Supply both contextual results and an explicit case map')
    if context:
        if context['season']!=board['season'] or date.fromisoformat(context['as_of'])>as_of:raise ValueError('Context date/season mismatch')
        lookup={(r['id'],r['case']):r for r in context['results']}
        for pid,cases in case_map.items():
            if set(cases)!={'baseline','downside'}:raise ValueError('Select both workload cases explicitly')
            overrides[pid]={}
            for case,label in cases.items():
                if (pid,label) not in lookup:raise ValueError('Selected contextual case not found')
                r=lookup[pid,label];games=float(r['appearances'])
                overrides[pid][case]=Exposure(games,float(r['points'])/games if games else 0)
    for row in board['players']:
        baseline=downside=None;warnings=[]
        if row['kind']=='goalie':
            g=review.get(row['id']);stat=rates['players'].get(row['id'],{}).get('start',{})
            if g and g['team']!=row['team']:raise ValueError('Reviewed team differs from board')
            if g and g['baseline_starts'] is not None and stat.get('shrunk_points') is not None:
                baseline=Exposure(float(g['baseline_starts']),stat['shrunk_points'])
                downside=Exposure(float(g['downside_starts']),stat['shrunk_points'])
                if stat['small_sample']:warnings.append('Small starter sample; experimental cohort shrinkage applied')
            else:warnings.append('Missing reviewed workload or starter sample; excluded from recommended picks')
            notes[row['id']]={'review':g,'starter_rate':stat,'warnings':warnings}
        elif row['projected_games'] is not None and row['points_per_game'] is not None:
            baseline=downside=Exposure(float(row['projected_games']),float(row['points_per_game']))
        if row['id'] in overrides:
            if row['kind']!='skater':raise ValueError('Context case map is for skaters; goalie budgets come from workload review')
            baseline=overrides[row['id']]['baseline'];downside=overrides[row['id']]['downside']
            notes[row['id']]={'context_cases':case_map[row['id']], 'warnings':['Season-average role scenario, not date-specific recovery or a fitted probability']}
        market=row.get('market')
        if market and (market['season']!=board['season'] or date.fromisoformat(market['as_of'])>as_of):raise ValueError('Future or wrong-season market input')
        result.append(DraftPlayer(row['id'],row['name'],row['team'],row['kind'],tuple(row['positions']),baseline,downside,
                                  float(market['value']) if market else None))
    if set(overrides)-{p.id for p in result}:raise ValueError('Unknown contextual player ID')
    return result,notes


def register(commands):
    p=commands.add_parser('draft-plan',help='Experimental two-turn draft choices with separate workload scenarios')
    for name in ('db','schedule','workloads','rates'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--context',type=Path);p.add_argument('--case-map',type=Path)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--opponents',choices=['rank','points','goalie_early'],default='rank')
    p.add_argument('--seeds',type=int,nargs='+',default=[0,1,2]);p.add_argument('--limit',type=int,default=6)
    p.add_argument('--output',type=Path,help='New immutable decision snapshot JSON')
    p.add_argument('--json',action='store_true')


def plan_session(path,schedule,workloads,rates,as_of,seeds=(0,1,2),style='rank',context=None,case_map=None):
    with connect(path) as db:
        info=settings(db);rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM players')]
        picks=[dict(r) for r in db.execute('SELECT * FROM picks ORDER BY pick')]
    if info['slot'] is None:raise ValueError('Set your draft slot first; rehearsal must use a separate database')
    board={**info['board'],'players':rows}
    if str(schedule['season'])!=board['season'][:4]+str(int(board['season'][:4])+1):raise ValueError('Schedule/board season mismatch')
    players,notes=build_players(board,workloads,rates,as_of,context,case_map)
    value=RosterValue(players,schedule,board['roster_slots'])
    result=compare_turns(players,picks,board['roster_slots'],info['teams'],info['slot'],value,seeds,style)
    for row in result['candidates']:row['projection_notes']=notes.get(row['id'],{})
    result['as_of']=as_of.isoformat();result['model']='two_turn_scenario_v1'
    result['session_state_sha256']=hashlib.sha256(json.dumps({'board':board,'picks':picks},sort_keys=True).encode()).hexdigest()
    result['warnings']+=['Starter rates replace per-appearance rates for goalies; relief starts/points are not added',
                        'Unmodified skaters have identical baseline/downside; scenario probabilities are not estimated',
                        'Live rankings and picks are unchanged; this advice is experimental']
    return result


def handle(args):
    if args.output and args.output.exists():raise ValueError('Decision snapshot already exists; choose a new path')
    if args.limit<1:raise ValueError('Limit must be positive')
    paths={k:getattr(args,k) for k in ('schedule','workloads','rates','context','case_map') if getattr(args,k)}
    inputs={k:json.loads(p.read_text()) for k,p in paths.items()}
    result=plan_session(args.db,inputs['schedule'],inputs['workloads'],inputs['rates'],args.as_of,args.seeds,args.opponents,inputs.get('context'),inputs.get('case_map'))
    result['code_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    result['input_sha256']={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as out:json.dump(result,out,indent=2)
    if args.json:print(json.dumps(result,indent=2));return 0
    print(f"Pick {result['pick']}, next turn {result['next_turn']} | experimental two-turn plan")
    print('Player                         Baseline gain   Downside gain')
    for row in result['candidates'][:args.limit]:
        print(f"{row['name']:30} {row['two_pick_gain']['baseline']:>13.1f} {row['two_pick_gain']['downside']:>15.1f}")
        notes=row['projection_notes']
        for warning in notes.get('warnings',[]):print('  '+warning)
        if notes.get('context_cases'):print('  Context cases: '+str(notes['context_cases']))
        if notes.get('starter_rate'):print(f"  Starter sample: {notes['starter_rate']['sample']}; relief excluded from exposure")
        for case in ('baseline','downside'):
            next_names=sorted({b['best_by_case'][case]['next_name'] or 'final pick' for b in row['branches']})
            print(f"  {case} later options: "+', '.join(next_names))
    if result.get('coverage_alternative'):
        alt=result['coverage_alternative']
        print(f"Coverage alternative: {alt['name']}, {alt['expected_failed_weeks']:.1f} expected failed calendar weeks, {alt['points_cost_vs_baseline_choice']:.1f} FP cost versus the point-maximizing choice (scenario estimates).")
    if result['baseline_choice']!=result['downside_choice']:print('Scenario-sensitive choice: baseline and downside favor different picks.')
    for warning in result['warnings']:print('NOTE: '+warning)
    return 0
