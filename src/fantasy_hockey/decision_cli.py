"""Read-only integration of the draft tracker, reviewed scenarios and two-turn search."""
from datetime import date
import hashlib
import json
from pathlib import Path
from dataclasses import replace
from time import perf_counter

from .draft import connect, settings
from .draft_value import DraftPlayer, Exposure, RosterValue
from .draft_planner import compare_turns
from .draft_completion import complete_draft
from .workload_review import validate_review


def working_snapshot(path):
    """Capture picks, player edits and revision in one SQLite read transaction."""
    with connect(path) as db:
        db.execute('BEGIN')
        info=settings(db)
        rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM players')]
        picks=[dict(r) for r in db.execute('SELECT * FROM picks ORDER BY pick')]
        revision=db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
    return {**info,'board':{**info['board'],'players':rows},'picks':picks,'revision':revision}


def working_players(board):
    from .preparation import recommendation_restrictions
    from .market import TEAM_ALIASES
    from .scoring import number
    as_of=date.fromisoformat(board['as_of'])
    players=[];stresses={}
    for row in board['players']:
        for evidence in (row.get('projection_evidence'),row.get('yahoo')):
            if evidence and evidence.get('as_of') and date.fromisoformat(evidence['as_of'])>as_of:raise ValueError('Future projection or market evidence')
        baseline=downside=None
        if not recommendation_restrictions(row,board):
            baseline=Exposure(float(number(row['projected_games'],'games')),float(number(row['points_per_game'],'rate')));downside=baseline
            review=row.get('review',{}).get('reference_scenarios')
            if review and review.get('baseline_points') is not None and review.get('downside_points') is not None:
                if date.fromisoformat(review['as_of'])>as_of:raise ValueError('Future scenario evidence')
                base=float(number(review['baseline_points'],'case baseline'));low=float(number(review['downside_points'],'case downside'))
                if base>0 and 0<=low<=base:
                    ratio=low/base;downside=Exposure(baseline.games,baseline.rate*ratio)
                    stresses[row['id']]={'factor':ratio,'as_of':review['as_of'],
                        'basis':'Working FP scaled by earlier reviewed downside/base FP ratio. GP unchanged; conditional aggregate stress, not a new forecast.'}
        yahoo=row.get('yahoo',{});adp=yahoo.get('adp')
        players.append(DraftPlayer(row['id'],row['name'],TEAM_ALIASES.get(row['team'],row['team']),row['kind'],tuple(row['positions']),baseline,downside,float(adp) if adp is not None else None))
    return players,stresses


def compare_working(snapshot, schedule):
    """Two-pick opportunity comparison using the frozen working forecast.

    No historical outcomes, projection fitting or roster mutations. Documented
    downside/base ratios are transferred as aggregate FP stresses, not GP changes
    or estimated probabilities. The same next pick is retained under stress.
    """
    from .draft import snake_team
    from .draft_planner import preferences, fits
    from .market import season_key
    started=perf_counter()
    board=snapshot['board'];seat=snapshot['slot'];teams=snapshot['teams'];picks=snapshot['picks']
    if seat is None:raise ValueError('Set your actual draft slot to compare picks')
    if snake_team(len(picks)+1,teams)!=seat:raise ValueError('Compare picks when your team is on the clock')
    if season_key(schedule['season'])!=season_key(board['season']):raise ValueError('Schedule season differs from board')
    if not schedule.get('games'):raise ValueError('Schedule is empty')
    as_of=date.fromisoformat(board['as_of'])
    if any(date.fromisoformat(g['date'])<=as_of for g in schedule['games'].values()):raise ValueError('Draft schedule must follow the board date')
    selected={p['player_id'] for p in picks}
    source={p['id']:p for p in board['players']}
    players,stresses=working_players(board)
    mapping={p.id:p for p in players};own=[p['player_id'] for p in picks if p['team']==seat]
    if any(mapping[pid].baseline is None for pid in own):raise ValueError('An owned player lacks a supported forecast or verified eligibility. Basic tracking remains available.')
    value=RosterValue(players,schedule,board['roster_slots'],draft_opportunity=True)
    if any(value.team_games[p.team]!=int(board['assumptions']['season_games']) for p in players if p.baseline):raise ValueError('Schedule does not contain a full season for every projected team')
    legal=[p for p in players if p.id not in selected and p.baseline and fits(p,own,mapping,board['roster_slots'])]
    if not legal:raise ValueError('No supported fitting candidates')
    raw=max(legal,key=lambda p:(p.baseline.games*p.baseline.rate,p.id))
    yahoo=min(legal,key=lambda p:(float(source[p.id].get('yahoo',{}).get('rank') or 1e9),p.id))
    # Shared preference orders across every candidate branch. These are distinct
    # hypotheses, not equally likely samples from an estimated distribution.
    orders={};labels={}
    for seed in (0,1):
        orders[seed]=preferences(players,seed,'rank');labels[seed]=f'ADP order with 10% jitter, seed {seed}'
    ranked=[replace(p,market_rank=float(source[p.id].get('yahoo',{}).get('rank') or 10000)) for p in players]
    orders[2]=[mapping[p.id] for p in preferences(ranked,0,'rank')];labels[2]='Yahoo displayed rank with 10% jitter'
    cautious=[replace(p,market_rank=float(source[p.id].get('yahoo',{}).get('rank') or 10000))
              if float(source[p.id].get('yahoo',{}).get('percent_drafted') or 0)<50 else p for p in players]
    orders[3]=[mapping[p.id] for p in preferences(cautious,1,'rank')];labels[3]='Low-drafted ADP replaced by displayed rank (sensitivity only)'
    # Include the best incremental player as well as the raw-points and market
    # baselines, so roster congestion can surface a player outside raw top tiers.
    initial=value.evaluate(own)['points']
    incremental=max(legal,key=lambda p:(value.evaluate(own+[p.id])['points']-initial,p.id))
    result=compare_turns(players,picks,board['roster_slots'],teams,seat,value,seeds=tuple(orders),
                         width=4,opponent_orders=orders,fixed_next_pick=True,
                         include_ids=(raw.id,yahoo.id,incremental.id))
    rows=result['candidates']
    best={(i,case):max(r['branches'][i]['best_by_case'][case]['value']['points'] for r in rows)
          for i in range(len(orders)) for case in ('baseline','downside')}
    for row in rows:
        p=mapping[row['id']];row['positions']=p.positions;row['team']=p.team
        row['season_points']=p.baseline.games*p.baseline.rate
        row['adp']=p.market_rank
        row['stress']=stresses.get(p.id)
        row['displaced_points']=max(0,row['season_points']-row['one_pick']['baseline']['gain'])
        row['max_regret']=max(best[i,case]-b['best_by_case'][case]['value']['points'] for i,b in enumerate(row['branches']) for case in ('baseline','downside'))
        row['scenarios_best']=sum(abs(best[i,'baseline']-b['best_by_case']['baseline']['value']['points'])<1e-7 for i,b in enumerate(row['branches']))
        gains=[b['best_by_case']['baseline']['value']['points']-initial for b in row['branches']]
        row['gain_range']=[min(gains),max(gains)]
        row['next_options']=[{'scenario':labels[b['seed']], 'id':b['best_by_case']['baseline']['next_id'],
                              'name':b['best_by_case']['baseline']['next_name'],'pair_gain':gains[i],
                              'stress_gain':b['best_by_case']['downside']['value']['points']-result['initial']['downside']['points']}
                             for i,b in enumerate(row['branches'])]
    robust=min(rows,key=lambda r:(r['max_regret'],-r['two_pick_gain']['baseline'],r['id']))
    refs={r['id']:r for r in rows}
    result.update(model='working_two_pick_opportunity_v1',revision=snapshot['revision'],
                  roster_aware_choice=incremental.id,points_choice=raw.id,yahoo_choice=yahoo.id,
                  robust_choice=robust['id'],scenario_labels=labels,
                  gain_vs_points=rows[0]['two_pick_gain']['baseline']-refs[raw.id]['two_pick_gain']['baseline'],
                  gain_vs_yahoo=rows[0]['two_pick_gain']['baseline']-refs[yahoo.id]['two_pick_gain']['baseline'],
                  stressed_player_count=len(stresses),as_of=board['as_of'],elapsed_seconds=perf_counter()-started,
                  session_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest(),
                  schedule_sha256=hashlib.sha256(json.dumps(schedule,sort_keys=True).encode()).hexdigest())
    result['warnings']=[
        'Experimental two-pick comparison, not a complete-draft optimum or a proven competitive advantage.',
        'Mean and ranges describe four chosen opponent hypotheses, not expected outcomes or calibrated survival probabilities.',
        'Season-average appearance fractions are matched to daily slots. Known scratches, replacement during injuries and confirmed goalie starts are not modeled.',
        'Goalie weekly qualification is deliberately separate: unfinished rosters are not penalized as finished teams. Verify the three-appearance minimum before completing your roster.',
        'Downside scales current FP by documented earlier case ratios. The same later pick is retained. Unmodified players are not risk-free.',
        'Bounded raw-value and positional shortlist, plus best current incremental option and baseline choices. Some two-player combinations are not searched.',
        'Later bench construction, streaming, playoff weighting and changing roles are outside this comparison.']
    return result


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
    for name in ('db','schedule'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('workloads','rates'):p.add_argument('--'+name,type=Path)
    p.add_argument('--working-board',action='store_true',help='Compare the frozen working forecasts with daily lineup opportunity')
    p.add_argument('--context',type=Path);p.add_argument('--case-map',type=Path)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--opponents',choices=['rank','points','goalie_early'],default='rank')
    p.add_argument('--seeds',type=int,nargs='+',default=[0,1,2]);p.add_argument('--limit',type=int,default=6)
    p.add_argument('--method',choices=['two-turn','completion'],default='two-turn')
    p.add_argument('--case',choices=['baseline','downside'],default='baseline',help='Scenario for full-draft completion')
    p.add_argument('--output',type=Path,help='New immutable decision snapshot JSON')
    p.add_argument('--json',action='store_true')


def plan_session(path,schedule,workloads,rates,as_of,seeds=(0,1,2),style='rank',context=None,case_map=None,method='two-turn',case='baseline'):
    with connect(path) as db:
        info=settings(db);rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM players')]
        picks=[dict(r) for r in db.execute('SELECT * FROM picks ORDER BY pick')]
    if info['slot'] is None:raise ValueError('Set your draft slot first; rehearsal must use a separate database')
    board={**info['board'],'players':rows}
    if str(schedule['season'])!=board['season'][:4]+str(int(board['season'][:4])+1):raise ValueError('Schedule/board season mismatch')
    players,notes=build_players(board,workloads,rates,as_of,context,case_map)
    value=RosterValue(players,schedule,board['roster_slots'])
    if method=='completion':
        result=complete_draft(players,picks,board['roster_slots'],info['teams'],info['slot'],value,seeds,style,case=case)
    elif method=='two-turn':
        result=compare_turns(players,picks,board['roster_slots'],info['teams'],info['slot'],value,seeds,style)
    else:
        raise ValueError('Unknown planning method')
    for row in result['candidates']:row['projection_notes']=notes.get(row['id'],{})
    result['as_of']=as_of.isoformat();result.setdefault('model','two_turn_scenario_v1')
    result['session_state_sha256']=hashlib.sha256(json.dumps({'board':board,'picks':picks},sort_keys=True).encode()).hexdigest()
    result['warnings']+=['Starter rates replace per-appearance rates for goalies; relief starts/points are not added',
                        'Unmodified skaters have identical baseline/downside; scenario probabilities are not estimated',
                        'Live rankings and picks are unchanged; this advice is experimental']
    return result


def handle(args):
    if args.output and args.output.exists():raise ValueError('Decision snapshot already exists; choose a new path')
    if args.limit<1:raise ValueError('Limit must be positive')
    if args.working_board:
        snapshot=working_snapshot(args.db)
        if date.fromisoformat(snapshot['board']['as_of'])>args.as_of:raise ValueError('Board is after analysis date')
        schedule=json.loads(args.schedule.read_text())
        if args.method=='completion':
            if not args.workloads or not args.rates:raise ValueError('Final-pick comparison requires reviewed workloads and starter rates')
            result=compare_working_completion(snapshot,schedule,json.loads(args.workloads.read_text()),json.loads(args.rates.read_text()))
        else:result=compare_working(snapshot,schedule)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('x') as out:json.dump(result,out,indent=2)
        if args.json:print(json.dumps(result,indent=2));return 0
        if args.method=='completion':
            print(f"Pick {result['pick']}: final-roster conditional comparison")
            for row in result['candidates'][:args.limit]:
                b=row['cases']['baseline'];d=row['cases']['downside']
                print(f"{row['name']}: {b['points']:.1f} baseline FP, {d['points']:.1f} downside FP; {b['failed_calendar_weeks_proxy']:.1f} failed calendar weeks (proxy)")
            for warning in result['warnings']:print('NOTE: '+warning)
            return 0
        print(f"Pick {result['pick']} to {result['next_turn']}: experimental two-pick opportunity comparison")
        for row in result['candidates'][:args.limit]:
            print(f"{row['name']}: {row['one_pick']['baseline']['gain']:.1f} added now; {row['two_pick_gain']['baseline']:.1f} mean pair gain; {row['max_regret']:.1f} maximum scenario regret")
        for warning in result['warnings']:print('NOTE: '+warning)
        return 0
    if not args.workloads or not args.rates:raise ValueError('Supply workload/rate inputs, or use --working-board')
    paths={k:getattr(args,k) for k in ('schedule','workloads','rates','context','case_map') if getattr(args,k)}
    inputs={k:json.loads(p.read_text()) for k,p in paths.items()}
    result=plan_session(args.db,inputs['schedule'],inputs['workloads'],inputs['rates'],args.as_of,args.seeds,args.opponents,inputs.get('context'),inputs.get('case_map'),args.method,args.case)
    result['code_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    result['input_sha256']={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as out:json.dump(result,out,indent=2)
    if args.json:print(json.dumps(result,indent=2));return 0
    if args.method=='completion':
        print(f"Pick {result['pick']} | experimental complete-draft rollout | {result['case']}")
        print('Player                         Completed roster FP   Missed weeks')
        for row in result['candidates'][:args.limit]:
            print(f"{row['name']:30} {row['expected_points']:>19.1f} {row['expected_failed_weeks']:>14.1f}")
        alt=next(r for r in result['candidates'] if r['id']==result['coverage_choice'])
        print(f"Coverage alternative: {alt['name']}, {alt['expected_failed_weeks']:.1f} expected missed weeks, {alt['points_cost_vs_best']:.1f} FP cost among compared plans.")
        for warning in result['warnings']:print('NOTE: '+warning)
        return 0
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


def working_starter_cases(board, workloads, rates):
    """Validate dated starter inputs without replacing the frozen board's GP."""
    as_of=date.fromisoformat(board['as_of']);validate_review(workloads,as_of)
    if workloads['season']!=board['season']:raise ValueError('Workload season differs from board')
    start=int(board['season'][:4])
    if rates['season']!=f'{start-1}{start}' or date.fromisoformat(rates['as_of'])>as_of:
        raise ValueError('Starter rates must precede the draft season')
    if board.get('config_sha256') and board['config_sha256'] not in rates.get('input_sha256',{}).values():
        raise ValueError('Starter-rate scoring differs from board')
    from .market import TEAM_ALIASES
    source={p['id']:p for p in board['players']};cases={}
    for g in workloads['goalies']:
        p=source.get(g['id']);rate=rates['players'].get(g['id'],{}).get('start',{}).get('shrunk_points')
        if not p or rate is None or g['baseline_starts'] is None:continue
        if TEAM_ALIASES.get(p['team'],p['team'])!=g['team']:continue
        cases[g['id']]={case:{'id':g['id'],'team':g['team'],'starts':g[case+'_starts'],'rate':float(rate)}
                        for case in ('baseline','downside')}
    return cases


def compare_working_completion(snapshot,schedule,workloads,rates):
    """Read-only final-pick alternative to the two-pick opportunity comparison."""
    from .draft_value import completion_options
    board=snapshot['board'];own=[r['player_id'] for r in snapshot['picks'] if r['team']==snapshot['slot']]
    capacity=sum(n for pos,n in board['roster_slots'].items() if pos not in {'IR','IR+'})
    if len(own)!=capacity-1:raise ValueError('Final-pick comparison requires exactly one roster place left')
    # Reuse the complete working-board, turn, source-date and schedule validation.
    ordinary=compare_working(snapshot,schedule)
    players,_=working_players(board);taken={r['player_id'] for r in snapshot['picks']}
    value=RosterValue(players,schedule,board['roster_slots'],draft_opportunity=True)
    result=completion_options(value,own,[p.id for p in players if p.id not in taken],working_starter_cases(board,workloads,rates))
    result.update(model='working_final_pick_coverage_v1',pick=ordinary['pick'],revision=snapshot['revision'],
                  as_of=board['as_of'],opportunity_choice=ordinary['baseline_choice'],
                  session_sha256=ordinary['session_sha256'],schedule_sha256=ordinary['schedule_sha256'],
                  review_sha256={k:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
                                 for k,v in [('workloads',workloads),('rates',rates)]})
    return result
