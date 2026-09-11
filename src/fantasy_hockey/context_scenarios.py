"""Conditional contextual scenarios. Inputs are analyst assumptions, not fitted forecasts."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping
from .scoring import number, score


@dataclass(frozen=True)
class Phase:
    appearances: Decimal
    rate_factors: Mapping[str, Decimal]


def project_phases(kind, rates, weights, phases, season_games=84):
    """Score mutually sequential phases; never add a second generic role bonus."""
    cap=number(season_games,'season games')
    if cap<=0:raise ValueError('Season games must be positive')
    score(kind,rates,weights)
    normalized={k:number(v,k) for k,v in rates.items()}
    total={k:Decimal(0) for k in normalized};games=Decimal(0)
    if not phases:raise ValueError('At least one phase required')
    for phase in phases:
        count=number(phase.appearances,'appearances')
        if count<0 or set(phase.rate_factors)-set(normalized):raise ValueError('Invalid phase exposure or stat factor')
        games+=count
        adjusted={k:v*number(phase.rate_factors.get(k,1),k) for k,v in normalized.items()}
        if any(number(v,'factor')<0 for v in phase.rate_factors.values()):raise ValueError('Negative stat factor')
        if kind=='skater' and adjusted.get('power_play_points',0)>adjusted.get('goals',0)+adjusted.get('assists',0):
            raise ValueError('PPP exceeds goals plus assists')
        if kind=='goalie' and any(adjusted.get(k,0)>1 for k in ('wins','shutouts')):
            raise ValueError('Goalie outcome rate exceeds one per appearance')
        for k,v in adjusted.items():total[k]+=v*count
    if games>cap:raise ValueError('Appearances exceed season length')
    scored=score(kind,total,weights)
    return {'appearances':games,'stats':total,'points':scored.total,
            'contributions':{c.stat:c.points for c in scored.contributions}}


def validate_evidence(case, as_of):
    if not case.get('assumptions') or not case.get('confirmation_needed') or not case.get('evidence'):
        raise ValueError('Scenario requires evidence, assumptions and confirmation conditions')
    for item in case['evidence']:
        if not item.get('source') or not item.get('fact'):raise ValueError('Evidence requires source and fact')
        if date.fromisoformat(item['date'])>as_of:raise ValueError('Future evidence')
    if date.fromisoformat(case['review_by'])<as_of:
        return ['Evidence assumptions overdue for review']
    return []


def allocate_starts(allocations, season_games):
    """Include reserve/other goalies explicitly, even when they lack projections."""
    values={pid:number(n,'starts') for pid,n in allocations.items()}
    if not values or any(n<0 for n in values.values()) or sum(values.values())!=number(season_games,'season games'):
        raise ValueError('Joint goalie starts must be nonnegative and sum to team games')
    return values


def evaluate(board, payload, as_of):
    if payload['season']!=board['season'] or date.fromisoformat(board['as_of'])>as_of:
        raise ValueError('Board season/date mismatch')
    target=int(board['season'].split('-')[0])
    if payload['prior_season']!=f'{target-1}{target}':raise ValueError('Conditional rates must use the previous season')
    players={p['id']:p for p in board['players']};results=[];seen=set()
    cap=board['assumptions']['season_games']
    for case in payload['skaters']:
        warnings=validate_evidence(case,as_of)
        key=(case['id'],case['name'])
        if key in seen:raise ValueError('Duplicate scenario')
        seen.add(key)
        p=players[case['id']]
        if p['kind']!='skater' or p['stats'] is None or number(p['projected_games'],'games')<=0:
            raise ValueError('Skater scenario requires complete positive-exposure baseline')
        rates={k:number(v,k)/number(p['projected_games'],'games') for k,v in p['stats'].items()}
        phases=[Phase(number(r['appearances'],'appearances'),r.get('rate_factors',{})) for r in case['phases']]
        projected=project_phases('skater',rates,board['scoring']['skater'],phases,cap)
        results.append({'id':p['id'],'player':p['name'],'case':case['name'],**projected,
                        'delta_from_baseline':projected['points']-number(p['projected_points'],'baseline'),
                        'stat_deltas':{k:v-number(p['stats'][k],k) for k,v in projected['stats'].items()},
                        'assumptions':case['assumptions'],'evidence':case['evidence'],
                        'confirmation_needed':case['confirmation_needed'],'review_by':case['review_by'],
                        'parameters':case['phases'],'warnings':warnings})
    for case in payload['goalie_teams']:
        warnings=validate_evidence(case,as_of)
        key=(case['team'],case['name'])
        if key in seen:raise ValueError('Duplicate scenario')
        seen.add(key)
        starts=allocate_starts(case['starts'],cap)
        for pid,n in starts.items():
            if pid=='other':continue
            p=players[pid];rates=payload['goalie_rates'][pid]
            if p['kind']!='goalie' or p['team']!=case['team']:raise ValueError('Goalie allocation identity/team conflict')
            if date.fromisoformat(rates['as_of'])>as_of or not rates.get('source'):
                raise ValueError('Goalie rates need dated provenance')
            if rates['season']!=payload['prior_season']:raise ValueError('Goalie rate season mismatch')
            relief=number(case.get('relief_appearances',{}).get(pid,0),'relief')
            start_stats=rates['per_start'];relief_stats=rates['per_relief']
            start_result=project_phases('goalie',start_stats,board['scoring']['goalie'],[Phase(n,{})],cap)
            if relief<0 or n+relief>number(cap,'cap'):raise ValueError('Invalid goalie appearances')
            if relief and relief_stats is None:raise ValueError('No rate evidence for projected relief appearances')
            relief_result=project_phases('goalie',relief_stats or start_stats,board['scoring']['goalie'],[Phase(relief,{})],cap)
            stats={k:start_result['stats'][k]+relief_result['stats'][k] for k in start_result['stats']}
            scored=score('goalie',stats,board['scoring']['goalie'])
            old_rate_points=(n+relief)*number(p['points_per_game'],'baseline rate')
            results.append({'id':pid,'player':p['name'],'case':case['name'],'points':scored.total,
                            'starts':n,'appearances':n+relief,'stats':stats,'team_allocation':starts,
                            'stat_deltas':{k:v-number(p['stats'][k],k) for k,v in stats.items()} if p.get('stats') else None,
                            'delta_from_baseline':scored.total-number(p['projected_points'],'baseline'),
                            'workload_only_delta':old_rate_points-number(p['projected_points'],'baseline'),
                            'conditional_rate_delta':scored.total-old_rate_points,
                            'rate_evidence':rates,'assumptions':case['assumptions'],'evidence':case['evidence'],
                            'confirmation_needed':case['confirmation_needed'],'review_by':case['review_by'],
                            'warnings':warnings+['Conditional start/relief rates from one season, not a fitted ability forecast',
                                                 'Reserve goalie points unprojected; allocation is complete but team scoring is not']})
    return {'season':payload['season'],'as_of':as_of.isoformat(),'model':'contextual_scenarios_v1','results':results,
            'warnings':['Conditional scenarios, not probability intervals; no most-likely case selected',
                        'Numeric exposures and rate changes are explicit analyst judgments, not values supplied by reporting',
                        'Whole-player season points, not usable lineup points or injury replacement value',
                        'Evidence motivates scenarios but does not validate their numerical parameters',
                        'Live board unchanged; no automatic promotion']}
