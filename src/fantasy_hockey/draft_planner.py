"""Bounded two-turn draft comparison. Opponents follow fixed noisy rank preferences."""
from collections import defaultdict
import random
from statistics import mean

from .draft import roster_assignment, snake_team
from .draft_value import scenario_points


def fits(player,roster,players,slots):
    rows=[players[pid].roster_row() for pid in roster]+[player.roster_row()]
    return len(roster_assignment(rows,slots))==len(rows)


def shortlist(available,roster,players,slots,case='baseline',width=6):
    order=sorted((p for p in available if getattr(p,case) is not None and fits(p,roster,players,slots)),
                 key=lambda p:(-scenario_points(p,case),p.id))
    chosen={p.id:p for p in order[:width]}
    # Include positional alternatives even when raw season points exclude them.
    for pos in ('C','LW','RW','D','G'):
        for p in [p for p in order if pos in p.positions][:2]:chosen[p.id]=p
    return list(chosen.values())


def preferences(players,seed,style):
    if style not in {'rank','points','goalie_early'}:raise ValueError('Unknown opponent style')
    rng=random.Random(seed)
    supported=[p for p in players if p.market_rank is not None]
    tail=max((p.market_rank for p in supported),default=0)
    fallback={p.id:tail+i for i,p in enumerate(sorted(players,key=lambda p:(-scenario_points(p),p.id)),1)}
    scores={}
    for p in sorted(players,key=lambda p:p.id):
        if style=='rank' and supported:
            score=-(p.market_rank or fallback[p.id])*rng.uniform(.9,1.1)
        else:
            score=scenario_points(p)
            if score==float('-inf'):score=-1e12
            score*=rng.uniform(.85,1.15)
            if style=='goalie_early' and p.kind=='goalie':score*=1.2
        scores[p.id]=score
    return sorted(players,key=lambda p:(-scores[p.id],p.id))


def simulate_until(order,rosters,selected,first,last,teams,players,slots):
    trace=[]
    for pick in range(first,last):
        team=snake_team(pick,teams)
        p=next((p for p in order if p.id not in selected and fits(p,rosters[team],players,slots)),None)
        if p is None:raise ValueError('Opponent simulation cannot complete a legal roster')
        selected.add(p.id);rosters[team].append(p.id)
        trace.append({'pick':pick,'team':team,'id':p.id})
    return trace


def compare_turns(players, picks, slots, teams, seat, value, seeds=(0,1,2), style='rank', width=6, opponent_orders=None, *, fixed_next_pick=False, include_ids=()):
    """No outcome inputs. Rank baseline and downside separately, never blend their likelihoods."""
    if not isinstance(seat,int) or not 1<=seat<=teams:raise ValueError('Set your actual draft slot before planning')
    if not seeds or len(set(seeds))!=len(seeds):raise ValueError('Use distinct opponent seeds')
    if width<1:raise ValueError('Positive shortlist width required')
    mapping={p.id:p for p in players};total=teams*sum(n for pos,n in slots.items() if pos not in {'IR','IR+'})
    next_pick=len(picks)+1
    if next_pick>total:raise ValueError('Draft complete')
    if snake_team(next_pick,teams)!=seat:raise ValueError('Two-turn advice is available when your team is on the clock')
    future=next((n for n in range(next_pick+1,total+1) if snake_team(n,teams)==seat),None)
    rosters=defaultdict(list);selected=set()
    for i,r in enumerate(picks,1):
        pid=r.get('id',r.get('player_id'))
        if r['pick']!=i or r['team']!=snake_team(i,teams) or pid in selected or pid not in mapping:raise ValueError('Invalid draft state')
        if not fits(mapping[pid],rosters[r['team']],mapping,slots):raise ValueError('Observed roster does not fit configured slots')
        selected.add(pid);rosters[r['team']].append(pid)
    own=rosters[seat]
    initial={case:value.evaluate(own,case) for case in ('baseline','downside')}
    available=[p for p in players if p.id not in selected]
    candidates={p.id:p for case in initial for p in shortlist(available,own,mapping,slots,case,width)}
    for pid in include_ids:
        if pid not in mapping or pid in selected or not fits(mapping[pid],own,mapping,slots):raise ValueError('Invalid comparison candidate')
        candidates[pid]=mapping[pid]
    if opponent_orders is not None and set(opponent_orders)!=set(seeds):raise ValueError('Opponent orders must match seeds')
    orders=opponent_orders or {seed:preferences(players,seed,style) for seed in seeds}
    for order in orders.values():
        if len(order)!=len(mapping) or {p.id for p in order}!=set(mapping):raise ValueError('Opponent order must contain each player exactly once')
    rows=[]
    for candidate in candidates.values():
        if candidate.baseline is None or candidate.downside is None:continue
        one={case:value.evaluate(own+[candidate.id],case) for case in initial}
        branches=[]
        for seed,order in orders.items():
            branch_rosters=defaultdict(list,{t:list(ids) for t,ids in rosters.items()})
            taken=selected|{candidate.id};branch_rosters[seat].append(candidate.id)
            trace=simulate_until(order,branch_rosters,taken,next_pick+1,future or next_pick+1,teams,mapping,slots)
            remaining=[p for p in players if p.id not in taken]
            best={}
            for case in initial:
                if fixed_next_pick and case=='downside':
                    chosen=best['baseline']['next_id']
                    best[case]={'next_id':chosen,'next_name':best['baseline']['next_name'],
                                'value':value.evaluate(branch_rosters[seat]+([chosen] if chosen else []),case)}
                    continue
                choices=shortlist(remaining,branch_rosters[seat],mapping,slots,case,width) if future else []
                scored=[(value.evaluate(branch_rosters[seat]+[p.id],case),p) for p in choices]
                chosen=max(scored,key=lambda pair:(pair[0]['points'],scenario_points(pair[1],case),pair[1].id)) if scored else None
                if future and chosen is None:raise ValueError('No projected fitting option at next turn')
                best[case]={'next_id':chosen[1].id if chosen else None,'next_name':chosen[1].name if chosen else None,
                            'value':chosen[0] if chosen else one[case]}
            branches.append({'seed':seed,'intervening_picks':trace,'best_by_case':best})
        rows.append({'id':candidate.id,'name':candidate.name,'kind':candidate.kind,
                     'one_pick':{case:{**one[case],'gain':one[case]['points']-initial[case]['points']} for case in initial},
                     'two_pick_gain':{case:mean(b['best_by_case'][case]['value']['points'] for b in branches)-initial[case]['points'] for case in initial},
                     'branches':branches})
    if not rows:raise ValueError('No supported fitting candidates')
    rows.sort(key=lambda r:(-r['two_pick_gain']['baseline'],r['id']))
    # Directly measure simulated survival, separately for each candidate-now branch.
    for row in rows:
        row['alternatives_surviving_to_next_turn']={pid:sum(pid not in {p['id'] for p in b['intervening_picks']} for b in row['branches'])/len(seeds)
                                                   for pid in candidates if pid!=row['id']} if future else {}
    coverage_alternative=None
    for row in rows:
        row['two_pick_coverage']={}
        for case in initial:
            outcomes=[b['best_by_case'][case] for b in row['branches']]
            failed=[o['value']['failed_weeks_proxy'] for o in outcomes]
            counts=[sum(mapping[pid].kind=='goalie' for pid in own+[row['id']]+([o['next_id']] if o['next_id'] else [])) for o in outcomes]
            row['two_pick_coverage'][case]={'expected_failed_weeks':mean(failed) if all(v is not None for v in failed) else None,'minimum_goalies':min(counts)}
    if any(mapping[pid].kind=='goalie' for pid in own):
        eligible=[r for r in rows if r['two_pick_coverage']['baseline']['minimum_goalies']>=2
                  and r['two_pick_coverage']['baseline']['expected_failed_weeks'] is not None]
        if eligible:
            alternative=min(eligible,key=lambda r:(r['two_pick_coverage']['baseline']['expected_failed_weeks'],-r['two_pick_gain']['baseline'],r['id']))
            coverage_alternative={'id':alternative['id'],'name':alternative['name'],
                                  'expected_failed_weeks':alternative['two_pick_coverage']['baseline']['expected_failed_weeks'],
                                  'points_cost_vs_baseline_choice':rows[0]['two_pick_gain']['baseline']-alternative['two_pick_gain']['baseline']}
    return {'coverage_alternative':coverage_alternative,'pick':next_pick,'next_turn':future,'seat':seat,'seeds':list(seeds),'opponent_style':style,'initial':initial,'candidates':rows,
            'baseline_choice':rows[0]['id'],'downside_choice':min(rows,key=lambda r:(-r['two_pick_gain']['downside'],r['id']))['id'],
            'warnings':['Two-turn search, not a complete-draft optimum; unfinished goalie rosters may be undervalued',
                        'Baseline and downside are separate conditional cases, with independently chosen next picks',
                        'Survival fractions describe synthetic opponents, not calibrated Yahoo ADP probabilities',
                        'Top raw-value candidates plus positional alternatives; unprojected candidates cannot be recommended',
                        'Calendar-week minimums, prior rates and expected lineup availability remain approximations']}
