"""Fetch a bounded, cached participation source sample. Never contacts Yahoo."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from threading import Event
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fantasy_hockey.history import seconds


def cache_source(path, url, limit=8_000_000):
    receipt_path = path.with_suffix(path.suffix + '.receipt.json')
    if path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['url'] != url or hashlib.sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
            raise ValueError('Cached source differs from receipt')
        return receipt
    with urlopen(Request(url, headers={'User-Agent': 'FantasyHockeyGM-PersonalResearch/0.1'}), timeout=30) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Source exceeds byte limit')
    if path.suffix == '.json':
        json.loads(raw)
    elif b'Playing Roster' not in raw:
        raise ValueError('Not an NHL playing roster report')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
    receipt = {'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
               'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
               'pregame_available_at': None}
    with receipt_path.open('x') as stream:
        json.dump(receipt, stream, indent=2)
    return receipt


def select_games(directory, year):
    def read(kind):
        with (directory / f'{kind}_{year}.csv').open() as stream:
            return list(csv.DictReader(stream))
    schedule = {r['game_id']: r for r in read('nhl_schedule') if r['game_type'] == 'R'}
    ordered = sorted(schedule, key=lambda g: (schedule[g]['game_time'], g))
    selected = []
    reasons = {}

    def add(gid, reason):
        if gid not in reasons:
            selected.append(gid)
            reasons[gid] = reason

    for gid in ordered[:10]:
        add(gid, 'first_ten_games')
    goalies = read('goalie_box')
    relief = {r['game_id'] for r in goalies if r['starter'].lower() == 'false' and seconds(r['toi']) > 0}
    for gid in ordered:
        if gid in relief and gid not in reasons and len(selected) < 20:
            add(gid, 'relief_appearance')
    rows = read('skater_box') + goalies
    previous = {}
    changes = set()
    for r in sorted((r for r in rows if r['game_id'] in schedule), key=lambda r: (schedule[r['game_id']]['game_time'], r['game_id'], r['player_id'])):
        old = previous.get(r['player_id'])
        if old and old != r['team_abbrev']:
            changes.add(r['game_id'])
        previous[r['player_id']] = r['team_abbrev']
    for gid in ordered:
        if gid in changes and gid not in reasons and len(selected) < 30:
            add(gid, 'observed_team_change_not_a_verified_transaction_date')
    for gid in ordered:
        if len(selected) < 30:
            add(gid, 'chronological_fill')
    return [{'game_id': gid, 'reason': reasons[gid]} for gid in selected]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--year', type=int, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--expand-from', type=Path, help='Verified 30-game pilot cache; expand to one regular season')
    p.add_argument('--validation-report', type=Path)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    selection_path = a.output_dir / 'selection.json'
    selection = select_games(a.directory, a.year)
    if a.expand_from:
        if not a.validation_report:
            raise ValueError('Expansion requires the pilot validation report')
        report = json.loads(a.validation_report.read_text())
        pilot_plan = a.expand_from / 'selection.json'
        prior = json.loads(pilot_plan.read_text())
        if (not report['expansion_ready'] or report['verified_games'] != 30
                or prior['ending_year'] != a.year
                or report['selection_sha256'] != hashlib.sha256(pilot_plan.read_bytes()).hexdigest()):
            raise ValueError('Pilot does not support this expansion')
        with (a.directory / f'nhl_schedule_{a.year}.csv').open() as stream:
            games = [r for r in csv.DictReader(stream) if r['game_type'] == 'R']
        selection = [{'game_id': r['game_id'], 'reason': 'one_season_after_verified_pilot'}
                     for r in sorted(games, key=lambda r: (r['game_time'], r['game_id']))]
    manifest = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for kind in ('nhl_schedule', 'skater_box', 'goalie_box')
                for path in [a.directory / f'{kind}_{a.year}.csv']}
    plan = {'selection': selection, 'inputs_sha256': manifest, 'ending_year': a.year}
    if a.expand_from:
        plan['pilot_validation_sha256'] = hashlib.sha256(a.validation_report.read_bytes()).hexdigest()
        if prior['inputs_sha256'] != manifest:
            raise ValueError('Season sources changed after pilot')
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != plan:
            raise ValueError('Selection changed; preserve prior evidence')
    else:
        with selection_path.open('x') as stream:
            json.dump(plan, stream, indent=2)

    stopped = Event()

    def fetch(case):
        gid = case['game_id']
        sources = [('json', f'https://raw.githubusercontent.com/sportsdataverse/fastRhockey-nhl-raw/main/nhl/json/final/{gid}.json'),
                   ('html', f'https://www.nhl.com/scores/htmlreports/{a.year-1}{a.year}/RO{gid[4:]}.HTM')]
        result = {'game_id': gid, 'sources': {}}
        for extension, url in sources:
            try:
                path = a.output_dir / f'{gid}.{extension}'
                if a.expand_from and not path.exists():
                    cached = a.expand_from / path.name
                    if cached.exists():
                        cache_source(cached, url)
                        shutil.copyfile(cached, path)
                        shutil.copyfile(cached.with_suffix(cached.suffix+'.receipt.json'), path.with_suffix(path.suffix+'.receipt.json'))
                if stopped.is_set() and not path.exists():
                    raise RuntimeError('Fetch suspended after provider access/rate-limit response')
                result['sources'][extension] = cache_source(path, url)
            except Exception as e:
                if isinstance(e, HTTPError) and e.code in (401, 403, 429):
                    stopped.set()
                result['sources'][extension] = {'error': type(e).__name__ + ': ' + str(e)}
        print(json.dumps({'game_id': gid, 'errors': [r['error'] for r in result['sources'].values() if 'error' in r]}), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, selection))
    with (a.output_dir / 'fetch-results.json').open('x') as stream:
        json.dump(results, stream, indent=2)


if __name__ == '__main__':
    main()
