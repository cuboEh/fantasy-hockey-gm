"""One-time raw-record audit; no fitting, source repair or pregame claims.

Run with --directory, --history-dir and a new --output-dir. Downloaded inputs
stay untouched. The recovered ledger contains outcomes, never live forecasts.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from fantasy_hockey.history import seconds


def key(row):
    return row['game_id'], row['player_id']


def exposure(row, kind):
    """Recover explicit fields, rejecting contradictory zero-time lines."""
    toi = seconds(row['toi'])
    conflicts = []
    if kind == 'goalie':
        flag = row['starter'].lower()
        if flag not in ('true', 'false'):
            raise ValueError('Unknown starter flag')
        started = flag == 'true'
        nonzero = any(int(row[k]) for k in ('saves', 'shots_against', 'goals_against'))
        if int(row['saves']) + int(row['goals_against']) != int(row['shots_against']):
            conflicts.append('Shots against do not reconcile; exclude scoring target until resolved')
        if toi == 0 and (started or nonzero or row.get('decision') in ('W', 'L', 'O')):
            raise ValueError('Zero-time goalie has appearance evidence')
    else:
        started = None
        nonzero = any(int(row[k]) for k in ('goals', 'assists', 'shots_on_goal', 'hits', 'shifts'))
        if toi == 0 and nonzero:
            raise ValueError('Zero-time skater has appearance evidence')
    return {'toi_seconds': toi, 'started': started, 'appeared': toi > 0, 'stat_conflicts': conflicts,
            'role': ('starter' if started else 'relief' if toi else 'unused_listed_goalie')
                    if kind == 'goalie' else 'appeared' if toi else 'zero_time_listed_skater'}


def audit_season(tables, year, normalized=None):
    expected = f'{year-1}{year}'
    issues = Counter()
    examples = defaultdict(list)

    def issue(label, identity):
        issues[label] += 1
        if len(examples[label]) < 8:
            examples[label].append(identity)

    raw_counts = {k: len(v) for k, v in tables.items()}
    usable = {}
    for name, rows in tables.items():
        usable[name] = []
        required = {'game_id', 'season_full' if name == 'nhl_schedule' else 'season'}
        for index, row in enumerate(rows):
            if not required.issubset(row):
                issue(name + '_missing_identity_columns', index)
            else:
                usable[name].append(row)
    tables = usable

    schedules = tables['nhl_schedule']
    games = {}
    for r in schedules:
        if r['season_full'] != expected:
            issue('schedule_wrong_season', r['game_id'])
            continue
        if r['game_type'] != 'R':
            continue
        if r['game_id'] in games:
            issue('duplicate_schedule_game', r['game_id'])
            raise ValueError('Duplicate regular-season schedule identity')
        if r['game_state'] not in ('OFF', 'FINAL'):
            issue('unfinished_game', r['game_id'])
            continue
        games[r['game_id']] = r
    all_game_ids = {r['game_id'] for r in schedules if r['season_full'] == expected}
    for name, rows in tables.items():
        if name == 'nhl_schedule':
            continue
        for r in rows:
            if r.get('season') != expected:
                issue(name + '_wrong_season', r.get('game_id'))
            if r['game_id'] not in all_game_ids:
                issue(name + '_unknown_game', r['game_id'])

    dedicated = {}
    counts = Counter()
    team_roles = defaultdict(Counter)
    ledger = []
    bad_keys = set()
    for name, kind in (('skater_box', 'skater'), ('goalie_box', 'goalie')):
        for r in tables[name]:
            gid, pid = key(r)
            if gid not in games or r['season'] != expected:
                continue
            identity = gid, pid
            if identity in dedicated:
                issue('duplicate_dedicated_player_game', identity)
                bad_keys.add(identity)
                continue
            dedicated[identity] = r
            g = games[gid]
            side = r.get('home_away')
            if side not in ('home', 'away') or r['team_abbrev'] != g[side + '_team_abbr']:
                issue('invalid_player_team_link', identity)
                bad_keys.add(identity)
                continue
            if r['game_date'] != g['game_date']:
                issue('player_schedule_date_mismatch', identity)
            try:
                recovered = exposure(r, kind)
            except (ValueError, KeyError, TypeError) as e:
                issue(str(e), identity)
                bad_keys.add(identity)
                continue
            counts[kind + '_' + recovered['role']] += 1
            for conflict in recovered['stat_conflicts']:
                issue(conflict, identity)
            team_roles[gid, r['team_abbrev']][kind] += 1
            if recovered['started']:
                team_roles[gid, r['team_abbrev']]['starters'] += 1
            ledger.append({'game_id': gid, 'id': pid, 'team': r['team_abbrev'], 'kind': kind,
                           'game_date': g['game_date'], 'game_start': g['game_time'],
                           **recovered, 'source_table': name,
                           'pregame_available_at': None, 'use': 'historical_outcome'})
    ledger = [r for r in ledger if (r['game_id'], r['id']) not in bad_keys]
    for gid, g in games.items():
        for team in (g['home_team_abbr'], g['away_team_abbr']):
            c = team_roles[gid, team]
            if c['starters'] != 1:
                issue('validated_team_game_starter_count_not_one', (gid, team, c['starters']))
            if c['skater'] == 0 or c['goalie'] == 0:
                issue('missing_team_kind_coverage', (gid, team))

    combined = {}
    for r in tables['player_box']:
        if r['game_id'] not in games or r['season'] != expected:
            continue
        if key(r) in combined:
            issue('duplicate_combined_player_game', key(r))
        combined[key(r)] = r
    for identity in sorted(dedicated.keys() - combined.keys()):
        issue('dedicated_missing_in_combined', identity)
    for identity in sorted(combined.keys() - dedicated.keys()):
        issue('combined_extra_player_game', identity)
    for identity in sorted(dedicated.keys() & combined.keys()):
        a, b = dedicated[identity], combined[identity]
        for field in ('toi', 'team_abbrev', 'starter', 'goals', 'assists', 'saves', 'shots_against', 'goals_against'):
            if field in a and a[field] != b.get(field):
                issue('combined_field_mismatch_' + field, identity)

    team_seen = set()
    sums = defaultdict(Counter)
    for r in dedicated.values():
        if 'shots_on_goal' in r:
            for stat in ('goals', 'shots_on_goal', 'hits'):
                sums[r['game_id'], r['team_abbrev']][stat] += int(r[stat])
    for r in tables['team_box']:
        if r['game_id'] not in games or r['season'] != expected:
            continue
        identity = r['game_id'], r['team_abbrev']
        if identity in team_seen:
            issue('duplicate_team_box', identity)
        team_seen.add(identity)
        for stat in ('goals', 'shots_on_goal', 'hits'):
            if sums[identity][stat] != int(r[stat]):
                issue('team_sum_mismatch_' + stat, identity)
    for gid, g in games.items():
        for team in (g['home_team_abbr'], g['away_team_abbr']):
            if (gid, team) not in team_seen:
                issue('missing_team_box', (gid, team))
    if normalized:
        norm = {(r['game_id'], r['id']): r for r in normalized['records']}
        recovered_keys = {(r['game_id'], r['id']) for r in ledger}
        for identity in sorted(norm.keys() - recovered_keys):
            issue('normalized_without_valid_exposure', identity)
        for r in ledger:
            n = norm.get((r['game_id'], r['id']))
            if n is None:
                issue('exposure_without_normalized_record', (r['game_id'], r['id']))
            elif n['appeared'] != r['appeared'] or n['team'] != r['team']:
                issue('normalized_participation_or_team_mismatch', (r['game_id'], r['id']))
    return {'ending_year': year, 'regular_games': len(games), 'raw_rows': raw_counts,
            'recovered_records': len(ledger), 'roles_before_duplicate_exclusions': dict(counts),
            'issues': dict(issues), 'examples': dict(examples),
            'normalized_available': normalized is not None}, ledger


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--history-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    reports, manifest = [], {}
    with (a.output_dir / 'exposure-outcomes.jsonl').open('x') as output:
        for schedule in sorted(a.directory.glob('nhl_schedule_*.csv')):
            year = int(schedule.stem.rsplit('_', 1)[1])
            tables = {}
            for kind in ('nhl_schedule', 'skater_box', 'goalie_box', 'player_box', 'team_box'):
                path = a.directory / f'{kind}_{year}.csv'
                raw = path.read_bytes()
                receipt_path = path.with_suffix('.metadata.json')
                receipt = json.loads(receipt_path.read_text())
                sha = hashlib.sha256(raw).hexdigest()
                if sha != receipt['sha256']:
                    raise ValueError(f'Input receipt mismatch: {path}')
                manifest[str(path)] = {'sha256': sha, 'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                                       'retrieved_at': receipt['retrieved_at']}
                with path.open(newline='', encoding='utf-8-sig') as stream:
                    tables[kind] = list(csv.DictReader(stream))
            history = a.history_dir / f'history-{year}.json'
            normalized = None
            if history.exists():
                raw = history.read_bytes()
                manifest[str(history)] = {'sha256': hashlib.sha256(raw).hexdigest()}
                normalized = json.loads(raw)
            report, ledger = audit_season(tables, year, normalized)
            for row in ledger:
                source = a.directory / f"{row.pop('source_table')}_{year}.csv"
                row['source_path'] = str(source)
                row['source_sha256'] = manifest[str(source)]['sha256']
                row['source_retrieved_at'] = manifest[str(source)]['retrieved_at']
                output.write(json.dumps(row) + '\n')
            reports.append(report)
            print(json.dumps({'year': year, 'recovered': len(ledger), 'issues': report['issues']}), flush=True)
    report = {'seasons': reports, 'inputs': manifest, 'model_fitted': False,
              'limitations': ['Zero-time labels concern explicit listed records only; missing player rows remain unknown.',
                              'Starter fields describe actual starters, not pregame confirmations.',
                              'Final rosters and schedules cannot establish historical pregame knowledge.',
                              'Team goals may include a shootout winner absent from player goal totals.',
                              'No full historical team membership or injury history inferred.']}
    (a.output_dir / 'report.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
