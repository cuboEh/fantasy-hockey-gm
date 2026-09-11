"""Chronological draft experiments. Current-pool results are diagnostic only."""

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
from pathlib import Path
import random
from statistics import mean, median

from .board import POSITIONS, read_json, season_lines
from .config import load_config
from .draft import snake_team
from .scoring import score


@dataclass(frozen=True)
class Model:
    shrink_games: int = 0
    workload_regression: float = 0.0
    strategy: str = 'points'
    workload_mode: str = 'fixed'

    @property
    def name(self):
        return f'shrink{self.shrink_games}_workload{self.workload_regression:g}_{self.strategy}_{self.workload_mode}'


@dataclass(frozen=True)
class Forecast:
    id: str
    name: str
    position: str
    kind: str
    rate: float
    games: float
    points: float


def historical_input(data, config, target):
    """Only pre-target seasons cross the draft information boundary.

    Position is the current source's primary position, an explicit unresolved
    metadata leak. Current ranks, teams, ages, flags and target stats are omitted.
    """
    if target not in {2024,2025,2026}:
        raise ValueError('This source adapter supports pre-draft history only from 2023 onward; older evaluation needs a complete historical adapter')
    result = []
    for group, kind in [('players', 'skater'), ('goalies', 'goalie')]:
        for row in data.get(group, []):
            prior = [s for s in row.get('seasons', []) if int(s['s'][:4]) < target]
            try:
                lines = season_lines({'seasons': prior}, kind, config.weights[kind])
            except (ValueError, KeyError):
                continue
            if not lines or row.get('pos') not in POSITIONS:
                continue
            history = [(int(s.season[:4]), float(s.games),
                        float(score(kind, s.stats, config.weights[kind]).total)) for s in lines]
            result.append((str(row['id']), row['name'], POSITIONS[row['pos']], kind, history))
    if len({p[0] for p in result}) != len(result):
        raise ValueError('Duplicate historical player identity')
    return result


def cohort_workload(history, identity, kind, previous_gp):
    """Five nearest historical usage transitions, excluding the target player.

    Caller supplies pre-draft history only. No sufficient cohort means no
    regression, not a universal goalie workload. This uses appearances, not starts.
    """
    pairs=[]
    for other, _, _, other_kind, lines in history:
        if other == identity or other_kind != kind:
            continue
        ordered=sorted(lines)
        for prior, later in zip(ordered,ordered[1:]):
            if later[0] == prior[0]+1:
                pairs.append((abs(prior[1]-previous_gp),other,prior[0],later[1]))
    nearest=sorted(pairs)[:5]
    return median(p[3] for p in nearest) if len(nearest)>=3 else previous_gp


def forecast(history, model):
    if model.workload_mode not in {'fixed','cohort'}:
        raise ValueError('Unknown workload mode')
    if model.shrink_games < 0 or not 0 <= model.workload_regression <= 1:
        raise ValueError('Invalid model parameters')
    # Per-appearance production prior uses only available historical observations.
    totals = Counter(); games = Counter()
    for _, _, pos, _, lines in history:
        for _, gp, points in lines:
            totals[pos] += points; games[pos] += gp
    result = []
    for identity, name, pos, kind, lines in history:
        lines = sorted(lines, reverse=True)
        weights = [(1 / 3) ** i for i in range(len(lines))]
        # Fixed recency decay, not tuned against the held-out season.
        mass = sum(weights)
        rate = sum(w * points / gp for w, (_, gp, points) in zip(weights, lines)) / mass
        gp = sum(w * gp for w, (_, gp, _) in zip(weights, lines)) / mass
        exposure = sum(gp for _, gp, _ in lines)
        rate = (rate * exposure + model.shrink_games * totals[pos] / games[pos]) / (exposure + model.shrink_games)
        typical = cohort_workload(history,identity,kind,gp) if model.workload_mode=='cohort' else (70 if kind == 'skater' else 45)
        gp = min(82, (1-model.workload_regression)*gp + model.workload_regression*typical)
        result.append(Forecast(identity, name, pos, kind, rate, gp, rate*gp))
    return result


def replacement_levels(pool, slots, teams):
    """Fixed active-slot depth heuristic, not estimated waiver-wire value."""
    result = {}
    for pos in {p.position for p in pool}:
        values = sorted((p.points for p in pool if p.position == pos), reverse=True)
        depth = teams * slots.get(pos, 0)
        result[pos] = values[min(depth, len(values)-1)]
    return result


def fits(counts, pos, slots):
    updated = counts.copy(); updated[pos] += 1
    return sum(max(0, n-slots.get(p, 0)) for p, n in updated.items()) <= slots.get('BN', 0)


def mock_draft(pool, opponent_pool, slots, teams, seat, seed, strategy, market=None, pick_value=None):
    """Outcome data is intentionally absent from this function's arguments."""
    if not 1 <= seat <= teams:
        raise ValueError('Invalid seat')
    rng = random.Random(seed)
    replacement = replacement_levels(pool, slots, teams)
    forecasts = {p.id:p for p in pool}
    # Synthetic opponents use a fixed historical-rate model with persistent player
    # preference noise. These rankings are not historical Yahoo ADP.
    preferences = {p.id:p.points * rng.uniform(0.85, 1.15) for p in sorted(opponent_pool, key=lambda p:p.id)}
    if market:
        # Supplied market ranks affect opponents only, never player production.
        tail=max(row['value'] for row in market.values())
        fallback={p.id:tail+i for i,p in enumerate(sorted(opponent_pool,key=lambda p:(-p.points,p.id)),1)}
        preferences={p.id:-market.get(p.id,{'value':fallback[p.id]})['value']*rng.uniform(0.9,1.1) for p in sorted(pool,key=lambda p:p.id)}
    own_order = sorted(pool, key=lambda p: (-(p.points - (replacement[p.position] if strategy=='replacement' else 0)), p.id))
    opponent_order = sorted(pool, key=lambda p:(-preferences[p.id], p.id))
    selected = set(); counts = [Counter() for _ in range(teams)]; picks = []
    rounds = sum(n for p,n in slots.items() if p not in {'IR','IR+'})
    for pick in range(1, teams*rounds+1):
        team = snake_team(pick, teams)
        order = own_order if team == seat else opponent_order
        candidates=(p for p in order if p.id not in selected and fits(counts[team-1], p.position, slots))
        if team==seat and pick_value is not None:
            from itertools import islice
            shortlist=list(islice(candidates,12))
            own_ids=[p['id'] for p in picks if p['team']==seat]
            player=max(shortlist,key=lambda p:(pick_value(p,own_ids),p.points,p.id)) if shortlist else None
        else:
            player=next(candidates,None)
        if player is None:
            raise ValueError('Historical pool cannot fill this draft')
        selected.add(player.id); counts[team-1][player.position] += 1
        picks.append({'pick':pick, 'team':team, 'id':player.id,
                      'name':player.name, 'forecast_points':forecasts[player.id].points})
    return picks


def outcomes(data, config, target):
    result = {}
    for group, kind in [('players','skater'), ('goalies','goalie')]:
        for row in data.get(group, []):
            target_rows = [s for s in row.get('seasons', []) if int(s['s'][:4]) == target]
            try:
                lines = season_lines({'seasons':target_rows}, kind, config.weights[kind])
            except (ValueError, KeyError):
                continue
            if lines:
                line = lines[0]
                result[str(row['id'])] = {'points':float(score(kind,line.stats,config.weights[kind]).total),
                                         'games':float(line.games), 'kind':kind}
    return result


def evaluate_picks(picks, actual, seat):
    own = [p for p in picks if p['team']==seat]
    missing = [p['id'] for p in own if p['id'] not in actual]
    return {'missing_outcome_ids':missing,
            'known_points':sum(actual[p['id']]['points'] for p in own if p['id'] in actual),
            'complete_points':None if missing else sum(actual[p['id']]['points'] for p in own),
            'players':len(own),
            'pick_outcomes':[{'id':p['id'],'pick':p.get('pick'),
                              'forecast_points':p.get('forecast_points'),
                              'actual_points':actual[p['id']]['points'] if p['id'] in actual else None}
                             for p in own]}


def experiment(data, config, target, model, scenarios):
    history = historical_input(data,config,target)
    predictions = forecast(history,model)
    # Opponents and the benchmark always use the same frozen model.
    opponent = forecast(history,Model())
    runs=[]
    for teams, seat, seed in scenarios:
        picks=mock_draft(predictions,opponent,dict(config.slots),teams,seat,seed,model.strategy)
        benchmark=mock_draft(opponent,opponent,dict(config.slots),teams,seat,seed,'points')
        # Outcomes are first read after draft decisions have been fixed.
        actual=outcomes(data,config,target)
        own=evaluate_picks(picks,actual,seat); base=evaluate_picks(benchmark,actual,seat)
        delta=None if own['complete_points'] is None or base['complete_points'] is None else own['complete_points']-base['complete_points']
        runs.append({'teams':teams,'seat':seat,'seed':seed,'result':own,'benchmark':base,'paired_delta':delta,'picks':picks})
    actual=outcomes(data,config,target)
    errors={}
    for kind in ('skater','goalie'):
        matched=[p for p in predictions if p.kind==kind and p.id in actual]
        errors[kind]={'n':len(matched),
                      'rate_mae':mean(abs(p.rate-actual[p.id]['points']/actual[p.id]['games']) for p in matched) if matched else None,
                      'total_mae':mean(abs(p.points-actual[p.id]['points']) for p in matched) if matched else None}
    return {'model':asdict(model),'target':target,'pool_size':len(predictions),'errors':errors,'runs':runs}


def run_study(data, config, seeds=1):
    if seeds < 1:
        raise ValueError('seeds must be positive')
    scenarios=[(teams,seat,seed) for teams in (12,13) for seat in range(1,teams+1) for seed in range(seeds)]
    models=[Model(shrink,workload,strategy) for shrink in (0,20) for workload in (0.0,0.5) for strategy in ('points','replacement')]
    training=[experiment(data,config,2024,m,scenarios) for m in models]
    # Fair selection uses exactly the same evaluable scenarios across all models.
    common=[i for i in range(len(scenarios)) if all(e['runs'][i]['paired_delta'] is not None for e in training)]
    if not common:
        raise ValueError('No common complete draft outcomes; cannot select a model')
    if len(common) != len(scenarios):
        raise ValueError('Incomplete tuning outcomes; resolve missing records before model selection')
    selection=[]
    for m,e in zip(models,training):
        selection.append({'name':m.name,'mean_paired_delta':mean(e['runs'][i]['paired_delta'] for i in common)})
    winner=max(range(len(models)),key=lambda i:selection[i]['mean_paired_delta'])
    # Only the locked winner sees the final season, never a second tuning grid.
    heldout=experiment(data,config,2025,models[winner],scenarios)
    paired=[r['paired_delta'] for r in heldout['runs'] if r['paired_delta'] is not None]
    return {'study_version':1,'status':'BIASED_CURRENT_POOL_DIAGNOSTIC_NOT_DEPLOYABLE',
            'objective':'Full-roster season totals, including bench; not realized lineup or H2H wins',
            'warnings':['Current player pool and positions contain survivorship/metadata leakage',
                        'Source omits some low-appearance seasons; missing outcomes are not zero',
                        'No daily lineups, streaming, goalie minimum enforcement, ADP or weekly matchups',
                        'Synthetic opponents; seeds and seats are correlated, not independent seasons',
                        '2025-26 was previously inspected in a rate diagnostic; this is not pristine unseen data',
                        'No model is promoted automatically from this experiment'],
            'selection_season':2024,'evaluation_season':2025,'common_selection_scenarios':len(common),
            'scenarios':len(scenarios),'selection':selection,'selected_model':asdict(models[winner]),
            'training':training,'evaluation':heldout,
            'evaluation_summary':{'complete_pairs':len(paired),
                                  'coverage_complete':len(paired)==len(scenarios),
                                  'mean_paired_delta':mean(paired) if len(paired)==len(scenarios) else None,
                                  'complete_case_mean_diagnostic_only':mean(paired) if paired else None,
                                  'min_delta':min(paired) if paired else None,'max_delta':max(paired) if paired else None}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,default=1)
    args=parser.parse_args()
    if args.output.resolve() in {args.input.resolve(),args.config.resolve()}:
        parser.error('Output cannot overwrite input')
    result=run_study(read_json(args.input),load_config(args.config),args.seeds)
    result['input_sha256']=hashlib.sha256(args.input.read_bytes()).hexdigest()
    result['config_sha256']=hashlib.sha256(args.config.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('status','selected_model','common_selection_scenarios','scenarios','evaluation_summary')},indent=2))


if __name__=='__main__':
    main()
