"""Paired retrospective daily/seven-day evaluation with pre-cutoff player cohorts.

No network, new model parameters, promotion, or reconstructed Yahoo transactions.
Final historical schedules and a reporting lag are explicit research assumptions.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tomllib

from fantasy_hockey.config import parse_config
from fantasy_hockey.gm_forecasts import BASELINE, CANDIDATE, RateHistory, estimate_participation
from fantasy_hockey.scoring import score
from research.evaluate_gm_rates import paired_interval


def utc_day(value):
    instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if instant.tzinfo is None:
        raise ValueError('Game start requires timezone')
    return instant.astimezone(timezone.utc).date().isoformat()


def prepare(histories, exposure, verified_games, weights):
    games, scoring_rows, conflicts = {}, {}, set()
    for history in histories:
        for gid, game in history['games'].items():
            if gid in games:
                raise ValueError('Duplicate historical game')
            games[gid] = dict(game, date=utc_day(game['start']))
        conflicts.update((r['game_id'], r['id']) for r in history.get('source_conflicts', []))
        for row in history['records']:
            key = row['game_id'], row['id']
            if key in scoring_rows:
                raise ValueError('Duplicate scoring player-game')
            game = games[row['game_id']]
            if row['team'] not in game['teams']:
                raise ValueError('Scoring team differs from game')
            score(row['kind'], row['stats'], weights[row['kind']])
            scoring_rows[key] = dict(row, date=game['date'])
    participation = []
    seen = set()
    for row in exposure:
        key = row['game_id'], row['id']
        if key in seen:
            raise ValueError('Duplicate participation player-game')
        seen.add(key)
        game = games[row['game_id']]
        if (row['team'] not in game['teams'] or utc_day(row['game_start']) != game['date']
                or row['kind'] not in weights or type(row['appeared']) is not bool):
            raise ValueError('Participation identity/date/kind mismatch')
        if row.get('stat_conflicts'):
            conflicts.add(key)
        if row['game_id'] in verified_games:
            participation.append(dict(row, date=game['date']))
    training = sorted((r for k, r in scoring_rows.items() if k not in conflicts),
                      key=lambda r: (r['date'], r['game_id'], r['id']))
    participation.sort(key=lambda r: (r['date'], r['game_start'], r['game_id'], r['id']))
    return games, scoring_rows, conflicts, training, participation


def forecast_window(engine, observations, games, cutoff, days):
    """Only already-matured observations enter the cohort or workload model."""
    mature_before = cutoff - timedelta(days=1)
    end = cutoff + timedelta(days=days)
    engine.advance(cutoff)
    if engine.rows and date.fromisoformat(engine.rows[-1]['date']) >= mature_before:
        raise ValueError('Rate history violates declared reporting lag')
    schedule = defaultdict(list)
    for gid, game in games.items():
        if cutoff.isoformat() <= game['date'] < end.isoformat():
            for team in game['teams']:
                schedule[team].append(gid)
    cases = []
    for pid in sorted(observations):
        prior = [r for r in observations[pid] if date.fromisoformat(r['date']) < mature_before]
        if not prior:
            continue
        last = max(prior, key=lambda r: (r['date'], r['game_start'], r['game_id']))
        if date.fromisoformat(last['date']) < cutoff - timedelta(days=30):
            continue
        kind = last['kind']
        if any(r['kind'] != kind for r in prior):
            raise ValueError('Player kind changes within participation history')
        if any(r['kind'] != kind for r in engine.own[pid]):
            raise ValueError('Scoring and participation player kinds differ')
        opportunities = sorted(schedule[last['team']])
        models = {}
        for label, version in (('baseline', BASELINE), ('candidate', CANDIDATE)):
            p = estimate_participation(prior, cutoff, version)['expected_appearances']
            rates = engine.rates(pid, kind, version)
            expected = p * len(opportunities)
            stats = {k: v * expected for k, v in rates.items()} if rates is not None else None
            models[label] = {'version': version, 'appearance_probability_per_opportunity': p,
                             'expected_appearances': expected,
                             'any_appearance_probability': 1-(1-p)**len(opportunities),
                             'rates': rates, 'expected_stats': stats,
                             'expected_points': float(score(kind, stats, engine.weights[kind]).total) if stats is not None else None}
        n = len(engine.own[pid])
        cases.append({'id': pid, 'kind': kind, 'cutoff': cutoff.isoformat(), 'days': days,
                      'end_exclusive': end.isoformat(), 'last_known_team': last['team'],
                      'last_membership_game': last['game_id'], 'last_membership_date': last['date'],
                      'history_available_before': mature_before.isoformat(), 'history_appearances': n,
                      'history_group': 'none' if not n else '1_9' if n < 10 else '10_29' if n < 30 else '30_plus',
                      'workload_observations': len(prior), 'forecast_game_ids': opportunities, 'models': models})
    return cases


def outcome_for(case, participation, scoring_rows, conflicts, weights):
    """Global NHL outcomes: no substitution of the forecast's last-known team."""
    rows = [r for r in participation if r['id'] == case['id']]
    appearances = sum(r['appeared'] for r in rows)
    stats = {k: 0.0 for k, v in weights[case['kind']].items() if v != 0}
    reasons = []
    for row in rows:
        if row['kind'] != case['kind']:
            raise ValueError('Forecast/outcome player kind differs')
        key = row['game_id'], row['id']
        source = scoring_rows.get(key)
        if key in conflicts:
            reasons.append('Conflicting scoring source: '+row['game_id'])
        elif row['appeared']:
            if source is None:
                reasons.append('Appeared without a scoring record: '+row['game_id'])
            elif source['appeared'] is not True:
                reasons.append('Scoring/participation appearance mismatch: '+row['game_id'])
            else:
                for k in stats:
                    stats[k] += float(source['stats'][k])
        elif source and any(float(v) != 0 for v in source['stats'].values()):
            reasons.append('Nonappearance has nonzero scoring: '+row['game_id'])
    return {'appearances': appearances, 'any_appearance': int(appearances > 0),
            'actual_game_ids': [r['game_id'] for r in rows if r['appeared']],
            'actual_teams': sorted({r['team'] for r in rows if r['appeared']}),
            'stats': None if reasons else stats,
            'points': None if reasons else float(score(case['kind'], stats, weights[case['kind']]).total),
            'scoring_exclusions': reasons}


class Metrics:
    def __init__(self):
        self.groups = {}

    def add(self, case, actual, weights):
        kind = case['kind']
        prefix = f"{case['days']}d:{kind}"
        groups = (prefix, prefix+':history_'+case['history_group'],
                  prefix+(':scheduled' if case['forecast_game_ids'] else ':no_scheduled_games'))
        block = date.fromisoformat(case['cutoff']).strftime('%G-%V')
        models = case['models']
        for group in groups:
            bucket = self.groups.setdefault(group, {'cases': 0, 'coverage': Counter(), 'metrics': {}, 'calibration': {}})
            bucket['cases'] += 1
            values = {}
            for label, model in models.items():
                delta = model['expected_appearances'] - actual['appearances']
                values.setdefault('appearance_mae', {})[label] = abs(delta)
                values.setdefault('appearance_bias', {})[label] = delta
                p = model['any_appearance_probability']
                values.setdefault('any_appearance_brier', {})[label] = (p-actual['any_appearance'])**2
                interval = min(int(p*10), 9)
                cal = bucket['calibration'].setdefault(label, {}).setdefault(interval, [0, 0.0, 0])
                cal[0] += 1; cal[1] += p; cal[2] += actual['any_appearance']
            supported = all(m['expected_points'] is not None for m in models.values())
            bucket['coverage']['scoring_forecast_supported' if supported else 'scoring_forecast_unsupported'] += 1
            bucket['coverage']['scoring_outcome_supported' if actual['points'] is not None else 'scoring_outcome_excluded'] += 1
            if not case['forecast_game_ids'] and actual['appearances']:
                bucket['coverage']['unexpected_appearance_without_scheduled_opportunity'] += 1
            if supported and actual['points'] is not None:
                for label, model in models.items():
                    delta = model['expected_points'] - actual['points']
                    values.setdefault('point_mae', {})[label] = abs(delta)
                    values.setdefault('point_bias', {})[label] = delta
                    for stat, prediction in model['expected_stats'].items():
                        values.setdefault('stat_mae:'+stat, {})[label] = abs(prediction-actual['stats'][stat])
                    if actual['appearances']:
                        predicted_rate = float(score(kind, model['rates'], weights[kind]).total)
                        values.setdefault('conditional_average_rate_point_mae', {})[label] = abs(predicted_rate-actual['points']/actual['appearances'])
            for metric, pair in values.items():
                m = bucket['metrics'].setdefault(metric, {'n': 0, 'baseline': 0.0, 'candidate': 0.0, 'blocks': {}})
                m['n'] += 1
                for label, value in pair.items():
                    m[label] += value
                b = m['blocks'].setdefault(block, [0.0, 0])
                b[0] += pair['candidate']-pair['baseline']; b[1] += 1

    def report(self):
        result = {}
        for name, bucket in sorted(self.groups.items()):
            metrics = {}
            for name_m, m in bucket['metrics'].items():
                metrics[name_m] = {'n': m['n'], 'baseline': m['baseline']/m['n'],
                                   'candidate': m['candidate']/m['n'],
                                   'candidate_minus_baseline': (m['candidate']-m['baseline'])/m['n'],
                                   'paired_week_interval': paired_interval(m['blocks']),
                                   'week_blocks': len(m['blocks'])}
            calibration = {label: {str(b): {'n': n, 'mean_probability': p/n, 'observed_fraction': y/n}
                                  for b, (n, p, y) in bins.items()}
                           for label, bins in bucket['calibration'].items()}
            result[name] = {'cases': bucket['cases'], 'coverage': dict(bucket['coverage']),
                            'metrics': metrics, 'calibration': calibration}
        return result


def evaluate(histories, exposure, verified_games, weights, start, end, emit, max_cases=300_000):
    games, scoring, conflicts, training, participation = prepare(histories, exposure, verified_games, weights)
    engine = RateHistory(weights)
    observations = defaultdict(list)
    coverage = Counter()
    metrics = Metrics()
    train_index = part_index = 0
    forecast_hash = hashlib.sha256()
    cutoff = date.fromisoformat(start)
    until = date.fromisoformat(end)
    by_day = defaultdict(list)
    for row in participation:
        by_day[row['date']].append(row)
    while cutoff < until:
        mature = (cutoff-timedelta(days=1)).isoformat()
        while train_index < len(training) and training[train_index]['date'] < mature:
            engine.add(training[train_index]); train_index += 1
        while part_index < len(participation) and participation[part_index]['date'] < mature:
            row = participation[part_index]
            observations[row['id']].append(row); part_index += 1
        for days in ((1, 7) if cutoff.weekday() == 0 and cutoff+timedelta(days=7) <= until else (1,)):
            window_end = (cutoff+timedelta(days=days)).isoformat()
            cases = forecast_window(engine, observations, games, cutoff, days)
            coverage['forecast_cases'] += len(cases)
            if coverage['forecast_cases'] > max_cases:
                raise ValueError('Declared case budget exhausted')
            forecast_hash.update(json.dumps(cases, sort_keys=True, separators=(',', ':')).encode())
            coverage[f'{days}d_windows'] += 1
            expected_games = {gid for gid, game in games.items() if cutoff.isoformat() <= game['date'] < window_end}
            if not expected_games <= verified_games:
                coverage[f'{days}d_missing_coverage_windows'] += 1
                coverage[f'{days}d_cases_restricted_by_missing_games'] += len(cases)
                for case in cases:
                    emit({'forecast': case, 'outcome': None, 'restriction': 'Incomplete NHL game coverage'})
                continue
            future = [r for day in sorted(by_day) if cutoff.isoformat() <= day < window_end for r in by_day[day]]
            future_by_player = defaultdict(list)
            for row in future:
                future_by_player[row['id']].append(row)
            chosen = {c['id'] for c in cases}
            active = {r['id'] for r in future if r['appeared']}
            coverage[f'{days}d_actual_appearing_player_windows'] += len(active)
            coverage[f'{days}d_actual_appearing_player_windows_outside_cohort'] += len(active-chosen)
            for case in cases:
                if coverage['evaluated_cases'] >= max_cases:
                    raise ValueError('Declared case budget exhausted')
                actual = outcome_for(case, future_by_player[case['id']], scoring, conflicts, weights)
                metrics.add(case, actual, weights)
                emit({'forecast': case, 'outcome': actual, 'restriction': None})
                coverage['evaluated_cases'] += 1
        cutoff += timedelta(days=1)
    return {'coverage': dict(coverage), 'metrics': metrics.report(), 'forecast_sha256': forecast_hash.hexdigest(),
            'promoted': False, 'baseline': BASELINE, 'candidate': CANDIDATE}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Preserve prior experiment; choose a new output directory')
    plan_raw = a.plan.read_bytes()
    plan = json.loads(plan_raw)
    raw = {}
    for path, expected in plan['inputs_sha256'].items():
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Declared experiment input changed: '+path)
        raw[path] = data
    histories = [json.loads(raw[f'var/history-{y}.json']) for y in (2024, 2025, 2026)]
    prefix = 'var/prd-2.0/p2-participation-audit/season-validation/'
    exposure = [json.loads(line) for line in raw[prefix+'participation-outcomes.jsonl'].splitlines()]
    validation = json.loads(raw[prefix+'report.json'])
    verified = {g['game_id'] for g in validation['games'] if g['status'] == 'verified'}
    expected_counts = {g['game_id']: g['records'] for g in validation['games'] if g['status'] == 'verified'}
    if Counter(r['game_id'] for r in exposure) != expected_counts:
        raise ValueError('Participation ledger differs from audited coverage')
    if plan['models'] != [BASELINE, CANDIDATE] or plan['cutoffs']['timezone'] != 'UTC':
        raise ValueError('Unsupported declared models or timezone')
    weights = parse_config(tomllib.loads(raw['config.local.toml'].decode('utf-8'))).weights
    a.output.mkdir(parents=True)
    with (a.output/'predictions-and-outcomes.jsonl').open('x') as stream:
        result = evaluate(histories, exposure, verified, weights, plan['cutoffs']['start'],
                          plan['cutoffs']['end_exclusive'], lambda row: stream.write(json.dumps(row)+'\n'))
    result['plan'] = plan
    result['plan_sha256'] = hashlib.sha256(plan_raw).hexdigest()
    result['implementation_sha256'] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__), Path('src/fantasy_hockey/gm_forecasts.py'),
                     Path('src/fantasy_hockey/scoring.py'), Path('research/evaluate_gm_rates.py'))}
    result['calibration_bins'] = 'Bins 0-8 are [i/10,(i+1)/10); bin 9 is [0.9,1].'
    result['limitations'] = ['Retrospective development comparison on previously inspected seasons, not independent validation.',
        'Final actual schedules and a two-calendar-date reporting lag are reconstructed availability assumptions.',
        'Post-game roster observations before cutoff select a recent-player cohort, not verified historical Yahoo eligibility.',
        'Seven-day UTC research windows are not verified Yahoo matchup boundaries.',
        'Appearance target is recorded positive ice time, not independently certified official games-played conventions.',
        'Any-appearance probability uses an independent-game approximation; no prediction intervals are claimed.',
        'Calendar-week bootstrap does not remove dependence across weeks; historical source corrections may also remain.',
        'No injuries, known starters, trades, opponent adjustments or outcomes inside the horizon update a frozen forecast.',
        'No automatic promotion or current league recommendations follow from this experiment.']
    (a.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'coverage': result['coverage'], 'forecast_sha256': result['forecast_sha256'], 'output': str(a.output)}))


if __name__ == '__main__':
    main()
