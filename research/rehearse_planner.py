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
from fantasy_hockey.draft_value import RosterValue
from fantasy_hockey.draft_planner import compare_turns, fits, preferences


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('board','schedule','workloads','rates','context','case-map','output-dir'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new output directory')
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
