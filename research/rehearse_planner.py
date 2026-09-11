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
    p.add_argument('--seats',type=int,nargs='+',default=[1,7,14]);p.add_argument('--teams',type=int,default=14)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new output directory')
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


if __name__=='__main__':main()
