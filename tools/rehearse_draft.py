"""Rehearse all draft slots locally; never open the real draft database."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import shutil
import tempfile
from time import perf_counter

from fantasy_hockey.board import read_json, dump_json
from fantasy_hockey import draft
from fantasy_hockey.preparation import point_order
from fantasy_hockey.backtest import Forecast
from fantasy_hockey.seasonlab import opportunity_evaluator


def simulate(board, teams, seed):
    rng=random.Random(seed)
    slots=board['roster_slots'];rounds=sum(n for p,n in slots.items() if p not in {'IR','IR+'})
    players=sorted(board['players'],key=point_order)
    market=[p for p in players if p.get('market')]
    # Never mix a partial market rank's numerical scale with point values.
    tail=max((float(p['market']['value']) for p in market),default=0)
    preferences={p['id']:(-float(p.get('market',{}).get('value',tail+i))*rng.uniform(.9,1.1) if market
                          else float(p['projected_points'] or 0)*rng.uniform(.85,1.15))
                 for i,p in enumerate(players,1)}
    order=sorted(players,key=lambda p:(p['projected_points'] is None and not p.get('market'),-preferences[p['id']],p['id']))
    rosters=defaultdict(list);selected=set();picks=[]
    for pick in range(1,teams*rounds+1):
        team=draft.snake_team(pick,teams)
        chosen=next((p for p in order if p['id'] not in selected and
                     len(draft.roster_assignment(rosters[team]+[p],slots))==len(rosters[team])+1),None)
        if chosen is None:raise ValueError(f'Insufficient eligible player coverage at pick {pick}')
        selected.add(chosen['id']);rosters[team].append(chosen)
        picks.append({'pick':pick,'team':team,'id':chosen['id'],'name':chosen['name']})
    for roster in rosters.values():
        active={p:n for p,n in slots.items() if p not in {'BN','IR','IR+'}}
        assert len(draft.roster_assignment(roster,active))==sum(active.values())
    return picks


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',type=Path,required=True);p.add_argument('--teams',type=int,default=14)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prior-calendar',type=Path,help='Previous season normalized history, for a shadow usable-game comparison')
    a=p.parse_args()
    if not 2<=a.teams<=32:p.error('Teams must be between 2 and 32')
    if a.output_dir.exists():p.error('Use a new rehearsal output directory')
    board=read_json(a.board);a.output_dir.mkdir(parents=True)
    scenarios=[simulate(board,a.teams,seed) for seed in (0,1,2)]
    seat_plans=[]
    for seat in range(1,a.teams+1):
        own=[[r for r in picks if r['team']==seat] for picks in scenarios]
        seat_plans.append({'slot':seat,'pick_numbers':[r['pick'] for r in own[0]],
                           'opening_four_round_scenarios':[picks[:4] for picks in own]})
    with tempfile.TemporaryDirectory() as directory:
        db=Path(directory)/'practice.sqlite';draft.initialize(db,a.board,a.teams,None)
        draft.set_slot(db,min(7,a.teams))  # Practice setting only, not Tristan's slot.
        durations=[]
        for item in scenarios[0]:
            start=perf_counter();actual=draft.pick_player(db,item['id']);durations.append(perf_counter()-start)
            assert actual==item
        assert draft.draft_board(db)['pick'] is None
        try:draft.pick_player(db,scenarios[0][0]['id'])
        except ValueError:pass
        else:raise AssertionError('Completed draft accepted an extra pick')
        removed=draft.undo(db);assert removed['player_id']==scenarios[0][-1]['id']
        draft.pick_player(db,removed['player_id'])
        duplicate_db=Path(directory)/'backup.sqlite';shutil.copy2(db,duplicate_db)
        assert draft.draft_board(db)==draft.draft_board(duplicate_db)
        draft.export_draft(db,a.output_dir/'rehearsal-export.json')
        shutil.copy2(db,a.output_dir/'rehearsal.sqlite')
    comparisons=[]
    if a.prior_calendar:
        previous=json.loads(a.prior_calendar.read_text())
        target_start=int(board['season'].split('-')[0])
        if previous.get('season') != f'{target_start-1}{target_start}':
            raise ValueError('Shadow comparison requires the immediately preceding season')
        season_games=float(board['assumptions']['season_games'])
        pool=[Forecast(p['id'],p['name'],p['positions'][0],p['kind'],float(p['points_per_game']),
                       float(p['projected_games'])*82/season_games,float(p['projected_points']))
              for p in board['players'] if p['projected_points'] is not None and len(p['positions'])==1]
        players={p['id']:p for p in board['players']}
        utility=opportunity_evaluator(pool,players,previous,board['roster_slots'])
        calendar_teams={t for game in previous['games'].values() for t in game['teams']}
        for seat in range(1,a.teams+1):
            for turn in [r for r in scenarios[0] if r['team']==seat][:4]:
                past=[r for r in scenarios[0] if r['pick']<turn['pick']]
                selected={r['id'] for r in past};own=[r['id'] for r in past if r['team']==seat]
                own_pool={p.id for p in pool}
                own_supported=[pid for pid in own if pid in own_pool]
                if len(own_supported)!=len(own):continue
                candidates=sorted((p for p in pool if p.id not in selected and players[p.id]['team'] in calendar_teams
                                   and len(draft.roster_assignment([players[pid] for pid in own]+[players[p.id]],board['roster_slots']))==len(own)+1),key=lambda p:(-p.points,p.id))[:12]
                scored=[{'id':p.id,'name':p.name,'season_points':p.points,
                         'prior_calendar_marginal_points':utility(p,own)*season_games/82} for p in candidates]
                comparisons.append({'slot':seat,'pick':turn['pick'],'baseline_top':scored[:3],
                                    'usable_top':sorted(scored,key=lambda p:(-p['prior_calendar_marginal_points'],p['id']))[:3]})
        (a.output_dir/'usable-shadow.json').write_text(dump_json({'comparisons':comparisons,
            'calendar_sha256':hashlib.sha256(a.prior_calendar.read_bytes()).hexdigest(),
            'warnings':['Previous calendar is a congestion proxy, not the 2026-27 schedule',
                        'Primary-position candidates only; top 12 fitting point-ranked candidates inspected',
                        'Shadow choices do not change simulated picks or live board',
                        'No injury adjustment; unsupported own rosters skipped']}))
    report={'teams':a.teams,'board_sha256':hashlib.sha256(a.board.read_bytes()).hexdigest(),
            'seeds':[0,1,2],'completed_picks_per_draft':len(scenarios[0]),
            'max_record_pick_seconds':max(durations),'seat_plans':seat_plans,
            'checks':['full snake order','all rosters fill active positions','persisted picks',
                      'completed draft rejects picks','undo and reenter','backup reopens identically'],
            'warnings':['Rank-following scenarios, not predictions of friends or model accuracy',
                        'Uses supplied market with synthetic fallback when available; otherwise historical point preferences',
                        'Injury flags do not change simulated choices; review before drafting',
                        'Rookies without projections or market data remain at the end of simulated rankings']}
    (a.output_dir/'report.json').write_text(dump_json(report))
    lines=['# Draft-slot rehearsal scenarios','',*report['warnings'],'']
    for row in seat_plans:
        lines += [f"## Slot {row['slot']}", 'Picks: '+', '.join(map(str,row['pick_numbers'])), '']
        for i,scenario in enumerate(row['opening_four_round_scenarios']):
            lines.append(f"Seed {i}: "+'; '.join(f"{r['pick']}: {r['name']}" for r in scenario))
        lines.append('')
    (a.output_dir/'seat-plans.md').write_text('\n'.join(lines)+'\n')
    print(dump_json({k:v for k,v in report.items() if k!='seat_plans'}))


if __name__=='__main__':main()
