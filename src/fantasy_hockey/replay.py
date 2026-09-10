"""Offline daily lineup replay from explicitly timestamped decision packets.

Decisions and outcomes are separate inputs. This fixed-roster replay does not
simulate acquisitions, Yahoo rolling locks, opponent lineups or market ADP.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import argparse
import hashlib
import json
from pathlib import Path

from .board import dump_json, read_json
from .config import load_config
from .scoring import number, score


def timestamp(value):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Timestamps must include a timezone')
    return result


@dataclass(frozen=True)
class Opportunity:
    player_id: str
    kind: str
    positions: tuple[str, ...]
    expected_points: Decimal


def select_lineup(players, slots):
    """Exact maximum expected-value assignment; bench earns no lineup points."""
    positions=tuple(sorted(p for p,n in slots.items() if p not in {'BN','IR','IR+'} and n))
    capacity=tuple(slots[p] for p in positions)
    # Each state retains score and a trace, allowing positional reassignment.
    states={(0,)*len(positions):(Decimal(0),())}
    for player in sorted(players,key=lambda p:p.player_id):
        updated=dict(states)
        for used,(value,trace) in states.items():
            for i,pos in enumerate(positions):
                if pos not in player.positions or used[i]>=capacity[i]:
                    continue
                next_used=list(used);next_used[i]+=1;next_used=tuple(next_used)
                candidate=(value+player.expected_points,trace+((player.player_id,pos),))
                if next_used not in updated or candidate[0]>updated[next_used][0]:
                    updated[next_used]=candidate
        states=updated
    value,trace=max(states.values(),key=lambda v:v[0])
    return {'expected_points':value,'assignments':dict(trace)}


def plan_days(decisions, slots):
    """This API cannot inspect actual points or appearance outcomes."""
    if decisions.get('schema_version') != 1:
        raise ValueError('Unsupported decision schema')
    plans=[]; seen=set(); previous=None
    for day in decisions['days']:
        lock=timestamp(day['lock_at'])
        if day['date'] in seen or (previous is not None and lock<=previous):
            raise ValueError('Days must have unique dates and increasing locks')
        seen.add(day['date']);previous=lock
        if lock.date().isoformat()!=day['date']:
            raise ValueError('Day date must match local lock date')
        if not day.get('week'):
            raise ValueError('Explicit league week is required')
        if timestamp(day['available_at'])>lock:
            raise ValueError('Decision data became available after lock')
        players=[];ids=set();kinds={}
        for row in day['players']:
            if row['id'] in ids:raise ValueError('Duplicate player')
            ids.add(row['id']);kinds[row['id']]=row['kind']
            if row['kind'] not in {'skater','goalie'}:raise ValueError('Invalid player kind')
            eligible=row['positions']
            if not eligible or set(eligible)-{'C','LW','RW','D','G'}:
                raise ValueError('Invalid eligibility')
            if (row['kind']=='goalie' and eligible!=['G']) or (row['kind']=='skater' and 'G' in eligible):
                raise ValueError('Eligibility conflicts with kind')
            if timestamp(row['available_at'])>lock or not row.get('source'):
                raise ValueError('Player forecast/eligibility needs pre-lock evidence')
            if type(row['scheduled']) is not bool:raise ValueError('scheduled must be boolean')
            if row['scheduled']:
                players.append(Opportunity(row['id'],row['kind'],tuple(eligible),number(row['expected_points'],'expected_points')))
        # Fixed roster: additions or removals need a future transaction policy.
        if plans and ids!=set(plans[0]['roster_ids']):
            raise ValueError('Fixed-roster replay cannot accept roster changes')
        if len(ids)>sum(n for p,n in slots.items() if p not in {'IR','IR+'}):
            raise ValueError('Roster exceeds active plus bench capacity')
        selected=select_lineup(players,slots)
        plans.append({'date':day['date'],'week':day['week'],'lock_at':day['lock_at'],
                      'roster_ids':sorted(ids),'scheduled_ids':[p.player_id for p in players],
                      'kinds':kinds,**selected})
    return plans


def settle(plans, outcomes, weights, minimum_goalie_appearances):
    if type(minimum_goalie_appearances) is not int or minimum_goalie_appearances<0:
        raise ValueError('Invalid goalie minimum')
    actual={}
    for row in outcomes['results']:
        key=(row['date'],row['id'])
        if key in actual:raise ValueError('Duplicate outcome')
        if type(row['appeared']) is not bool or not row.get('source'):
            raise ValueError('Outcome requires appearance flag and source')
        if not row['appeared'] and any(number(v,'nonappearance stats')!=0 for v in row['stats'].values()):
            raise ValueError('Nonappearance cannot have nonzero statistics')
        actual[key]=row
    weeks={}; days=[]
    for plan in plans:
        week=weeks.setdefault(plan['week'],{'skater_points':Decimal(0),'goalie_points':Decimal(0),
                                           'bench_points':Decimal(0),'goalie_appearances':0,'missing':[]})
        for identity in plan['scheduled_ids']:
            row=actual.get((plan['date'],identity))
            if row is None:
                week['missing'].append({'date':plan['date'],'id':identity})
                continue
            kind=plan['kinds'][identity]
            points=score(kind,row['stats'],weights[kind]).total if row['appeared'] else Decimal(0)
            if identity in plan['assignments']:
                week[kind+'_points']+=points
                if kind=='goalie' and row['appeared']:week['goalie_appearances']+=1
            else:
                week['bench_points']+=points
        days.append(plan)
    for week in weeks.values():
        week['complete']=not week['missing']
        week['lineup_points']=week['skater_points']+week['goalie_points'] if week['complete'] else None
        week['goalie_minimum_met']=week['goalie_appearances']>=minimum_goalie_appearances if week['complete'] else None
        # Do not invent Yahoo's penalty semantics while those remain unverified.
        week['rule_qualified_points']=week['lineup_points'] if week['goalie_minimum_met'] else None
    return {'days':days,'weeks':weeks,'minimum_goalie_appearances':minimum_goalie_appearances,
            'warnings':['Fixed-roster daily global-lock replay; not Yahoo rolling-lock emulation',
                        'No transaction policy, opponent matchups or H2H win estimate',
                        'Missing outcomes invalidate weekly totals, never silently zero-filled',
                        'Goalie minimum failures flagged; platform penalty semantics not assumed',
                        'Input timestamps and source claims require independent verification']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('decisions','outcomes','config','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--goalie-minimum',type=int,required=True)
    args=parser.parse_args()
    if args.output.resolve() in {args.decisions.resolve(),args.outcomes.resolve(),args.config.resolve()}:
        parser.error('Output cannot overwrite an input')
    config=load_config(args.config)
    plans=plan_days(read_json(args.decisions),config.slots)
    result=settle(plans,read_json(args.outcomes),config.weights,args.goalie_minimum)
    result['input_hashes']={k:hashlib.sha256(getattr(args,k).read_bytes()).hexdigest() for k in ('decisions','outcomes','config')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(dump_json(result))
    print(f'Replayed {len(plans)} days; report: {args.output}')


if __name__=='__main__':main()
