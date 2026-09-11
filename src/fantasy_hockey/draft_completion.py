"""Complete-draft rollouts using only pre-draft scenarios and synthetic opponents."""
from collections import defaultdict
from statistics import mean
from functools import lru_cache

from .backtest import Forecast
from .draft import snake_team
from .draft_planner import compare_turns, fits, preferences, shortlist
from .draft_value import scenario_points
from .goalie_coverage import coverage_evaluator


def continuation_utility(players, value, case='baseline'):
    """Reuse insurance selection with starter exposures, preserving early goalie value."""
    pool=[]
    metadata={}
    for p in players:
        exp=getattr(p,case)
        if exp is None:
            continue
        games=value.team_games[p.team]
        pool.append(Forecast(p.id,p.name,p.positions[0],p.kind,exp.rate,
                             exp.games*82/games,exp.games*exp.rate))
        metadata[p.id]={'team':p.team}
    utility=coverage_evaluator(pool,metadata,value.calendar,value.slots)
    mapping={p.id:p for p in pool}
    @lru_cache(maxsize=20000)
    def cached(pid,own):
        return utility(mapping[pid],own)
    return lambda candidate, own: cached(candidate.id,tuple(sorted(own)))


def complete_draft(players,picks,slots,teams,seat,value,seeds=(0,1,2),style='rank',
                   width=4,opponent_orders=None,case='baseline'):
    """Compare terminal rosters under one fixed continuation policy, not an optimum.

Opponent orders are held fixed across candidate branches. Outcomes are not an
input. The historical runner must keep realized preferences out of planning.
"""
    # Reuse draft-state checks; this small comparison also supplies a diverse shortlist.
    checked=compare_turns(players,picks,slots,teams,seat,value,seeds,style,width,
                          opponent_orders)
    mapping={p.id:p for p in players}
    if case not in {'baseline','downside'}:
        raise ValueError('Unknown scenario')
    if opponent_orders is not None and set(opponent_orders)!=set(seeds):
        raise ValueError('Opponent orders must match the planning seeds')
    orders=opponent_orders or {s:preferences(players,s,style) for s in seeds}
    utility=continuation_utility(players,value,case)
    start=len(picks)+1
    total=teams*sum(v for p,v in slots.items() if p not in {'IR','IR+'})
    original=defaultdict(list)
    selected=set()
    for pick in picks:
        pid=pick.get('id',pick.get('player_id'))
        original[pick['team']].append(pid)
        selected.add(pid)
    @lru_cache(maxsize=30000)
    def legal_fit(pid,roster):
        return fits(mapping[pid],roster,mapping,slots)
    own=original[seat]
    if any(getattr(mapping[pid],case) is None for pid in own):
        raise ValueError('Owned player lacks the requested scenario')
    candidate_ids=[r['id'] for r in checked['candidates']]
    supported=sorted((p for p in players if getattr(p,case) is not None),
                     key=lambda p:(-scenario_points(p,case),p.id))
    rows=[]
    for pid in candidate_ids:
        branches=[]
        for seed,order in orders.items():
            rosters=defaultdict(list,{t:list(ids) for t,ids in original.items()})
            taken=selected|{pid}
            rosters[seat].append(pid)
            trace=[{'pick':start,'team':seat,'id':pid}]
            for number in range(start+1,total+1):
                team=snake_team(number,teams)
                if team==seat:
                    legal=[p for p in supported if p.id not in taken and
                           legal_fit(p.id,tuple(sorted(rosters[team])))]
                    if not legal:
                        raise ValueError('Cannot complete a supported own roster')
                    # Same bounded, positional shortlist for every branch.
                    choices=shortlist(legal,rosters[team],mapping,slots,case,width)
                    chosen=max(choices,key=lambda p:(utility(p,rosters[team]),
                                                      scenario_points(p,case),p.id))
                else:
                    chosen=next((p for p in order if p.id not in taken and
                                 legal_fit(p.id,tuple(sorted(rosters[team])))),None)
                    if chosen is None:
                        raise ValueError('Cannot complete opponent roster')
                taken.add(chosen.id)
                rosters[team].append(chosen.id)
                trace.append({'pick':number,'team':team,'id':chosen.id})
            branches.append({'seed':seed,'own_roster':rosters[seat],
                             'goalie_ids':[pid for pid in rosters[seat] if mapping[pid].kind=='goalie'],
                             'value':value.evaluate(rosters[seat],case),'picks':trace})
        rows.append({'id':pid,'name':mapping[pid].name,'branches':branches,
                     'expected_points':mean(b['value']['points'] for b in branches),
                     'expected_failed_weeks':mean(b['value']['failed_weeks_proxy'] or 0 for b in branches),
                     'point_range':[min(b['value']['points'] for b in branches),max(b['value']['points'] for b in branches)],
                     'goalie_count_range':[min(len(b['goalie_ids']) for b in branches),max(len(b['goalie_ids']) for b in branches)]})
    rows.sort(key=lambda r:(-r['expected_points'],r['expected_failed_weeks'],r['id']))
    for row in rows:
        row['points_cost_vs_best']=rows[0]['expected_points']-row['expected_points']
    safer=min(rows,key=lambda r:(r['expected_failed_weeks'],-r['expected_points'],r['id']))
    return {'model':'complete_draft_v1','pick':start,'case':case,'choice':rows[0]['id'],
            'coverage_choice':safer['id'],'candidates':rows,'seeds':list(seeds),
            'warnings':['Full-draft rollout under a fixed insurance continuation policy, not an optimal draft',
                        'Synthetic opponent preferences are uncertain; terminal values are scenario estimates',
                        'No streaming or future news is modeled; calendar-week and lineup approximations remain']}
