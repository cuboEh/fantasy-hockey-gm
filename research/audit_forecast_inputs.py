"""Audit saved normalized history before choosing a GM forecast experiment.

Unobserved player-games are not confirmed absences. This command does not fit,
score a policy, repair source records or establish an untouched test set.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path

from fantasy_hockey.config import load_config
from fantasy_hockey.scoring import score


FEATURES = ('toi_seconds', 'pp_toi_seconds', 'expected_goals', 'started',
            'source_observed_at', 'injury_status', 'linemates')


def audit_history(history, weights):
    games, records = history['games'], history['records']
    seen = set()
    duplicate = 0
    invalid_links = 0
    invalid_dates = 0
    participation = defaultdict(Counter)
    stat_errors = Counter()
    stat_error_examples = {}
    feature_records = Counter()
    team_days = defaultdict(set)
    observed = defaultdict(set)
    kind_by_player = {}
    for game in games.values():
        day = date.fromisoformat(game['date'])
        for team in game['teams']:
            team_days[team].add((day, game['id']))
    for row in records:
        identity = (row['game_id'], row['id'])
        duplicate += identity in seen
        seen.add(identity)
        kind = row['kind']
        kind_by_player[row['id']] = kind
        value = row.get('appeared')
        participation[kind]['appeared' if value is True else 'explicit_nonappearance' if value is False else 'unknown'] += 1
        game = games.get(row['game_id'])
        if game is None or row['team'] not in game['teams']:
            invalid_links += 1
        elif row['date'] != game['date']:
            invalid_dates += 1
        else:
            observed[row['id'], row['team']].add((date.fromisoformat(row['date']), row['game_id']))
        try:
            score(kind, row['stats'], weights[kind])
        except (KeyError, ValueError, TypeError) as exc:
            stat_errors[kind] += 1
            stat_error_examples.setdefault(kind, str(exc))
        for key in FEATURES:
            if row.get(key) is not None:
                feature_records[key] += 1
    gaps = Counter()
    players_with_gaps = set()
    for (player, team), entries in observed.items():
        first, last = min(d for d, _ in entries), max(d for d, _ in entries)
        absent = {entry for entry in team_days[team] if first <= entry[0] <= last} - entries
        if absent:
            gaps[kind_by_player[player]] += len(absent)
            players_with_gaps.add(player)
    return {
        'ending_year': history['ending_year'], 'games': len(games), 'records': len(records),
        'players': len(kind_by_player), 'participation_records': dict(participation),
        'duplicate_player_games': duplicate, 'invalid_game_team_links': invalid_links,
        'record_schedule_date_mismatches': invalid_dates,
        'unscorable_records': dict(stat_errors), 'stat_error_examples': stat_error_examples,
        'normalized_feature_records': {key: feature_records[key] for key in FEATURES},
        'unobserved_between_same_team_records': dict(gaps), 'players_with_unobserved_intervals': len(players_with_gaps),
        'source_conflicts': len(history.get('source_conflicts', [])),
        'source_conflict_types': dict(Counter(c.get('issue', 'unspecified') for c in history.get('source_conflicts', []))),
        'source_warnings': history.get('warnings', []),
        'interpretation': 'Within-team observation intervals are candidate gaps, not proof of injury, scratches, roster membership or missing source rows.',
        'independent_holdout_verified': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, nargs='+', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve prior audit evidence; choose a new output path')
    config = load_config(args.config)
    results, inputs, years = [], {}, set()
    for path in args.history:
        raw = path.read_bytes()
        history = json.loads(raw)
        year = history['ending_year']
        if year in years:
            raise ValueError('Duplicate historical season')
        years.add(year)
        inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        results.append(audit_history(history, config.weights))
    result = {'seasons': sorted(results, key=lambda r: r['ending_year']), 'input_sha256': inputs,
              'config_sha256': hashlib.sha256(args.config.read_bytes()).hexdigest(),
              'model_fitted': False, 'recommendations_changed': False,
              'limitations': ['Source completeness is not established by a scorable observed line.',
                              'Missing player-games cannot be zero-filled as actual absences.',
                              'Prior research used these seasons; chronology does not make them untouched.',
                              'A future exposure or context model needs additional dated fields.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'seasons': len(results), 'records': sum(r['records'] for r in results),
                      'output': str(args.output), 'model_fitted': False}))


if __name__ == '__main__':
    main()
