"""Exercise all draft seats with two-turn advice and real persistence in isolated databases."""
import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from time import perf_counter

from fantasy_hockey import draft
from fantasy_hockey.decision_cli import build_players, plan_session
from fantasy_hockey.decision_cli import working_players, compare_working
from fantasy_hockey.draft_value import RosterValue
from fantasy_hockey.draft_planner import compare_turns, fits, preferences


def rehearse_working(board,schedule,seats,teams,output):
    """Compare policies under one additional synthetic opponent order.

    Fixed current forecasts, not NHL outcomes. This is a decision diagnostic,
    not historical predictive validation or evidence of a competitive edge.
    """
    players,_=working_players(board);mapping={p.id:p for p in players}
    source={p['id']:p for p in board['players']};slots=board['roster_slots']
    order=preferences(players,33,'rank')  # Not one of the four planning hypotheses.
    total=teams*sum(n for pos,n in slots.items() if pos not in {'IR','IR+'})
    results=[]
    for seat in seats:
        for policy in ('points','yahoo','two-pick'):
            picks=[];selected=set();rosters=defaultdict(list);decisions=[]
            value=RosterValue(players,schedule,slots,draft_opportunity=True)
            for n in range(1,total+1):
                team=draft.snake_team(n,teams)
                if team==seat:
                    legal=[p for p in players if p.id not in selected and p.baseline and fits(p,rosters[seat],mapping,slots)]
                    if policy=='two-pick':
                        result=compare_working({'board':board,'teams':teams,'slot':seat,'picks':picks,'revision':n-1},schedule)
                        chosen=mapping[result['baseline_choice']]
                        decisions.append({'pick':n,'choice':chosen.id,'points_choice':result['points_choice'],
                                          'gain_vs_points':result['gain_vs_points'],'seconds':result['elapsed_seconds']})
                    elif policy=='points':chosen=max(legal,key=lambda p:(p.baseline.games*p.baseline.rate,p.id))
                    else:chosen=min(legal,key=lambda p:(float(source[p.id].get('yahoo',{}).get('rank') or 1e9),p.id))
                else:chosen=next(p for p in order if p.id not in selected and fits(p,rosters[team],mapping,slots))
                selected.add(chosen.id);rosters[team].append(chosen.id)
                picks.append({'pick':n,'team':team,'player_id':chosen.id})
            own=rosters[seat];evaluated=value.evaluate(own)
            row={'seat':seat,'policy':policy,'roster':own,'value':evaluated,
                 'goalie_count':sum(mapping[pid].kind=='goalie' for pid in own),
                 'goalie_projected_appearances':sum(mapping[pid].baseline.games for pid in own if mapping[pid].kind=='goalie'),
                 'sum_season_points':sum(mapping[pid].baseline.games*mapping[pid].baseline.rate for pid in own),
                 'decisions':decisions}
            results.append(row)
            (output/f'seat-{seat}-{policy}.json').write_text(json.dumps({'result':row,'picks':picks},indent=2))
            print(f"Seat {seat}, {policy}: {evaluated['points']:.1f} lineup proxy FP",flush=True)
    return {'results':results,'opponent_seed':33,
            'interpretation':'Full-draft current-forecast decision diagnostic against one additional synthetic opponent order; not realized NHL results.',
            'warnings':['Three chosen draft slots are not representative of all leagues.',
                        'Using the same forecast/value model to choose and score rosters cannot demonstrate predictive accuracy.',
                        'Final goalie counts/appearances do not establish weekly minimum coverage.',
                        'Two-pick search may sacrifice later positional depth. No weights tuned to these results.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('board','schedule','output-dir'):p.add_argument('--'+key,type=Path,required=True)
    for key in ('workloads','rates','context','case-map'):p.add_argument('--'+key,type=Path)
    p.add_argument('--working-board',action='store_true')
    p.add_argument('--audit-working',type=Path,help='Audit existing working diagnostic picks without rerunning drafts')
    p.add_argument('--seats',type=int,nargs='+',default=[1,7,14]);p.add_argument('--teams',type=int,default=14)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new output directory')
    if a.audit_working:
        if not a.workloads or not a.rates:p.error('Completion audit needs workloads and rates')
        board=json.loads(a.board.read_text());schedule=json.loads(a.schedule.read_text())
        if date.fromisoformat(board['as_of'])>a.as_of:p.error('Future board')
        audit_working(board,schedule,json.loads(a.workloads.read_text()),json.loads(a.rates.read_text()),a.audit_working,a.output_dir,a.seats,a.teams)
        return
    if a.working_board:
        if not 2<=a.teams<=32 or any(not 1<=seat<=a.teams for seat in a.seats):p.error('Invalid teams/seats')
        board=json.loads(a.board.read_text());schedule=json.loads(a.schedule.read_text())
        if date.fromisoformat(board['as_of'])>a.as_of:p.error('Future board')
        a.output_dir.mkdir(parents=True)
        report=rehearse_working(board,schedule,a.seats,a.teams,a.output_dir)
        report['input_sha256']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (a.board,a.schedule)}
        report['code_sha256']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in Path('src/fantasy_hockey').glob('*.py')}
        (a.output_dir/'report.json').write_text(json.dumps(report,indent=2));return
    if any(getattr(a,k) is None for k in ('workloads','rates','context','case_map')):p.error('Supply review inputs or use --working-board')
    inputs={k:json.loads(getattr(a,k).read_text()) for k in ('board','schedule','workloads','rates','context','case_map')}
    players,_=build_players(inputs['board'],inputs['workloads'],inputs['rates'],a.as_of,inputs['context'],inputs['case_map'])
    slots=inputs['board']['roster_slots'];mapping={p.id:p for p in players}
    order=preferences(players,0,'rank');a.output_dir.mkdir(parents=True);results=[]
    for seat in range(1,15):
        value=RosterValue(players,inputs['schedule'],slots)
        picks=[];selected=set();rosters=defaultdict(list);durations=[];advice_rows=[]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'practice.sqlite';draft.initialize(path,a.board,14,seat)
            for n in range(1,225):
                team=draft.snake_team(n,14)
                if team==seat:
                    start=perf_counter()
                    advice=compare_turns(players,picks,slots,14,seat,value,seeds=(0,),style='rank')
                    durations.append(perf_counter()-start);chosen=mapping[advice['baseline_choice']]
                    advice_rows.append({'pick':n,'candidate':chosen.id,'baseline_choice':advice['baseline_choice'],
                                        'downside_choice':advice['downside_choice'], 'top':advice['candidates'][:3]})
                    # One persisted advice call per seat verifies integration with tracked picks.
                    if len(advice_rows)==8:
                        before=path.read_bytes()
                        loaded=plan_session(path,inputs['schedule'],inputs['workloads'],inputs['rates'],a.as_of,(0,),'rank',inputs['context'],inputs['case_map'])
                        assert loaded['baseline_choice']==chosen.id and before==path.read_bytes()
                        backup=Path(tmp)/'backup.sqlite';shutil.copy2(path,backup)
                        assert draft.draft_board(backup)==draft.draft_board(path)
                else:chosen=next(p for p in order if p.id not in selected and fits(p,rosters[team],mapping,slots))
                actual=draft.pick_player(path,chosen.id)
                picks.append({'pick':n,'team':team,'id':chosen.id,'name':chosen.name})
                assert actual==picks[-1]
                selected.add(chosen.id);rosters[team].append(chosen.id)
            assert draft.draft_board(path)['pick'] is None
            last=draft.undo(path);draft.pick_player(path,last['player_id'])
            draft.export_draft(path,a.output_dir/f'seat-{seat}-export.json')
            # Export can reconstruct all player payloads and pick order.
            exported=json.loads((a.output_dir/f'seat-{seat}-export.json').read_text())
            recovered_board=Path(tmp)/'recovered-board.json'
            recovered_board.write_text(json.dumps({**exported['settings']['board'],'players':exported['players']}))
            restored=Path(tmp)/'restored.sqlite';draft.initialize(restored,recovered_board,14,seat)
            for r in exported['picks']:draft.pick_player(restored,r['player_id'])
            assert draft.draft_board(restored)==draft.draft_board(path)
        result={'seat':seat,'picks':len(picks),'own_decisions':len(durations),'max_advice_seconds':max(durations),
                'scenario_disagreements':sum(r['baseline_choice']!=r['downside_choice'] for r in advice_rows),
                'own_roster':rosters[seat]}
        results.append(result);(a.output_dir/f'seat-{seat}-advice.json').write_text(json.dumps(advice_rows,indent=2))
        print('Rehearsed seat',seat,'max advice',round(max(durations),2),flush=True)
    report={'results':results,'input_sha256':{k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in inputs},
            'checks':['224 legal picks per seat','all own decisions recomputed','persisted mid-draft advice agrees and does not mutate DB',
                      'backup reopens','undo/reentry','export rebuild restores roster and pick order'],
            'warning':'Synthetic rank-following rehearsal verifies workflow, not future model accuracy; no live draft database opened.'}
    (a.output_dir/'report.json').write_text(json.dumps(report,indent=2))



def audit_working(board,schedule,workloads,rates,previous,output,seats,teams):
    """Final-pick coverage tradeoffs and assumption-sensitive review priorities."""
    from fantasy_hockey.decision_cli import working_starter_cases
    from fantasy_hockey.draft_value import completion_options
    if not seats or len(set(seats))!=len(seats) or any(not 1<=s<=teams for s in seats):raise ValueError('Invalid audit seats')
    players,stresses=working_players(board);mapping={p.id:p for p in players}
    cases=working_starter_cases(board,workloads,rates)
    value=RosterValue(players,schedule,board['roster_slots'],draft_opportunity=True)
    source={p['id']:p for p in board['players']};reports=[];reviews=defaultdict(list)
    prior_report=json.loads((previous/'report.json').read_text())
    # Refuse to audit drafts made against a different frozen board or calendar.
    expected=prior_report['input_sha256'].values()
    for payload,name in ((board,'board'),(schedule,'schedule')):
        # Original files are identified by their payloads, not by assumed paths.
        paths=[Path(p) for p in prior_report['input_sha256']]
        matched=[p for p in paths if p.exists() and json.loads(p.read_text())==payload]
        if not any(hashlib.sha256(p.read_bytes()).hexdigest() in expected for p in matched):
            raise ValueError('Diagnostic input mismatch: '+name)
    output.mkdir(parents=True)
    for seat in seats:
        prior=previous/f'seat-{seat}-two-pick.json';saved=json.loads(prior.read_text());picks=saved['picks']
        own_picks=[r for r in picks if r['team']==seat]
        if len(picks)!=teams*16 or len(own_picks)!=16:raise ValueError('Expected a completed 16-round rehearsal')
        final=own_picks[-1];before=picks[:final['pick']-1];taken={r['player_id'] for r in before}
        held=[r['player_id'] for r in before if r['team']==seat]
        options=completion_options(value,held,[p.id for p in players if p.id not in taken],cases)
        options['seat']=seat;options['original_final_pick']=final['player_id']
        reference=next((r for r in options['candidates'] if r['id']==final['player_id']),None)
        for row in options['candidates']:
            row['delta_vs_original']={case:{key:row['cases'][case][key]-reference['cases'][case][key]
                for key in ('points','skater_points','qualified_goalie_points','failed_calendar_weeks_proxy')}
                for case in ('baseline','downside')} if reference else None
        reports.append(options)
        (output/f'seat-{seat}-completion.json').write_text(json.dumps(options,indent=2))
        print('Completed final-pick audit',seat,flush=True)
        decisions=[]
        for turn in own_picks:
            advice=compare_working({'board':board,'teams':teams,'slot':seat,'picks':picks[:turn['pick']-1],'revision':turn['pick']-1},schedule)
            ids={advice[k] for k in ('baseline_choice','downside_choice','robust_choice','points_choice')}
            top=next(r for r in advice['candidates'] if r['id']==advice['baseline_choice'])
            summary={'seat':seat,'pick':turn['pick'],'baseline':advice['baseline_choice'],
                     'downside':advice['downside_choice'],'robust':advice['robust_choice'],
                     'max_regret':top['max_regret'],'gain_vs_points':advice['gain_vs_points']}
            decisions.append(summary)
            if len({summary['baseline'],summary['downside'],summary['robust']})>1:
                for row in advice['candidates']:
                    if row['id'] in ids:
                        reviews[row['id']].append({**summary,'candidate_max_regret':row['max_regret'],
                            'conditional_pair_loss':row['two_pick_gain']['baseline']-row['two_pick_gain']['downside']})
        (output/f'seat-{seat}-sensitivity.json').write_text(json.dumps(decisions,indent=2))
        print('Completed sensitivity audit',seat,flush=True)
    priorities=[]
    for pid,decisions in reviews.items():
        row=source[pid]
        priorities.append({'id':pid,'name':row['name'],'kind':row['kind'],'adp':mapping[pid].market_rank,
            'affected_decisions':len(decisions),'maximum_choice_regret':max(r['max_regret'] for r in decisions),
            'stress':stresses.get(pid),'existing_review':row.get('review'),
            'review_question':'Verify start share and competition, and compare the lost bench skater.' if row['kind']=='goalie' else
                'Check projected GP and role; assess whether the alternative survives to the next turn.',
            'decisions':decisions})
    priorities.sort(key=lambda r:(-r['maximum_choice_regret'],-r['affected_decisions'],r['id']))
    report={'completion':reports,'review_priorities':priorities,
        'warnings':['Same frozen current forecasts, not realized results. No weights tuned.',
                    'Final-pick alternatives are available at that historical rehearsal turn; not promised available in the real draft.',
                    'Review frequency reflects three chosen seats, not player injury or model error probabilities.',
                    'Existing evidence is exposed for follow-up, not claimed to be newly researched.'],
        'source_files_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [previous/'report.json']+[previous/f'seat-{s}-two-pick.json' for s in seats]},
        'payload_sha256':{k:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest() for k,v in [('board',board),('schedule',schedule),('workloads',workloads),('rates',rates)]},
        'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in list(Path('src/fantasy_hockey').glob('*.py'))+[Path(__file__)]}}
    (output/'report.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
