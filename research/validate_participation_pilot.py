"""Pure reconciliation of saved NHL roster reports, raw games and season boxes.

Post-game roster membership is an outcome cohort, not historical pregame input.
"""
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata

from research.audit_participation_records import exposure


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children).strip()

    def nodes(self, tag):
        for c in self.children:
            if isinstance(c, Node):
                if c.tag == tag:
                    yield c
                yield from c.nodes(tag)


class RosterHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in ('meta', 'img', 'br', 'hr', 'input', 'link'):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def name_key(value):
    value = re.sub(r'\s*\([AC]\)\s*$', '', value.upper())
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if c.isascii() and c.isalnum())


def parse_report(html, game_id, game_date):
    parser = RosterHTML()
    parser.feed(html)
    text = parser.root.text()
    d = date.fromisoformat(game_date)
    if not re.search(r'Game\s+' + str(int(game_id[-4:])).zfill(4) + r'\b', text):
        raise ValueError('Official report game number mismatch')
    if f'{d.strftime("%B")} {d.day}, {d.year}' not in text or 'Final' not in text:
        raise ValueError('Official report date/final state mismatch')
    blocks = []
    block_tables = {}
    for table in parser.root.nodes('table'):
        rows = []
        for tr in table.children:
            if not isinstance(tr, Node) or tr.tag != 'tr':
                continue
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag == 'td']
            if len(cells) == 3:
                rows.append(cells)
        if not rows or [c.text() for c in rows[0]] != ['#', 'Pos', 'Name']:
            continue
        block = []
        for cells in rows[1:]:
            number, position, name = [c.text() for c in cells]
            if not number.isdigit() or position not in ('C', 'L', 'R', 'D', 'G'):
                raise ValueError('Unsupported roster report player row')
            block.append({'number': int(number), 'position': position, 'name': name,
                          'bold': 'bold' in cells[0].attrs.get('class', '').split()})
        blocks.append(block)
        block_tables[table] = block
    scratch_sections = [n for n in parser.root.nodes('tr') if n.attrs.get('id') == 'Scratches']
    if scratch_sections:
        if len(scratch_sections) != 1:
            raise ValueError('Ambiguous scratch section')
        section = scratch_sections[0]
        cells = [n for n in section.children if isinstance(n, Node) and n.tag == 'td']
        if len(cells) != 2:
            raise ValueError('Expected two scratch team cells')
        scratch_tables = set(section.nodes('table'))
        dressed_blocks = [block for table, block in block_tables.items() if table not in scratch_tables]
        if len(dressed_blocks) != 2:
            raise ValueError('Expected two dressed roster tables')
        scratch_blocks = []
        for cell in cells:
            found = [block_tables[n] for n in cell.nodes('table') if n in block_tables]
            if len(found) == 1:
                scratch_blocks.append(found[0])
            elif not found and not cell.text().strip():
                scratch_blocks.append([])
            else:
                raise ValueError('Unrecognized empty scratch report cell')
        blocks = dressed_blocks + scratch_blocks
    if len(blocks) != 4:
        raise ValueError(f'Expected dressed and scratch tables for both teams, found {len(blocks)}')
    return dict(zip(('away_dressed', 'home_dressed', 'away_scratches', 'home_scratches'), blocks))


def validate_game(raw, html, saved_rows, game_id, schedule, identity_reviews=()):
    errors = []
    ledger = []
    reviewed = {(r['game_id'], r['team'], r['id']): name_key(r['report_name']) for r in identity_reviews}
    try:
        box = raw['boxscore_raw']
        pbp = raw['pbp_raw']
        if str(box['id']) != game_id or str(pbp['id']) != game_id:
            raise ValueError('Raw game identity mismatch')
        if str(box['season']) != schedule['season_full'] or box['gameDate'] != schedule['game_date']:
            raise ValueError('Raw season/date mismatch')
        if box['gameState'] not in ('OFF', 'FINAL') or box['gameType'] != 2:
            raise ValueError('Expected final regular-season game')
        report = parse_report(html, game_id, box['gameDate'])
        ids = [str(r['playerId']) for r in pbp['rosterSpots']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate dressed NHL player identity')
        saved = {r['player_id']: r for r in saved_rows}
        if len(saved) != len(saved_rows):
            raise ValueError('Duplicate saved player identity')
        raw_ids = set()
        all_scratch_ids = set()
        for side in ('away', 'home'):
            team = box[side+'Team']
            if team['abbrev'] != schedule[side+'_team_abbr']:
                raise ValueError('Raw team differs from schedule')
            players = [r for r in pbp['rosterSpots'] if r['teamId'] == team['id']]
            jerseys = {r['sweaterNumber']: r for r in players}
            if len(jerseys) != len(players):
                raise ValueError('Ambiguous team jersey identity')
            dressed = report[side+'_dressed']
            if len(dressed) != len(players):
                raise ValueError('Official/raw dressed roster count mismatch')
            verified = set()
            bold_goalies = set()
            for r in dressed:
                p = jerseys.get(r['number'])
                if p is None:
                    raise ValueError('Official dressed identity mismatch')
                pid = str(p['playerId'])
                if name_key(r['name']) != name_key(p['firstName']['default']+' '+p['lastName']['default']) and reviewed.get((game_id, team['abbrev'], pid)) != name_key(r['name']):
                    raise ValueError('Official dressed identity mismatch')
                if pid in verified:
                    raise ValueError('Duplicate official dressed identity')
                if r['position'] != p['positionCode']:
                    raise ValueError('Official/raw roster position mismatch')
                verified.add(pid)
                if r['position'] == 'G' and r['bold']:
                    bold_goalies.add(pid)
            stats = box['playerByGameStats'][side+'Team']
            flat = stats['forwards'] + stats['defense'] + stats['goalies']
            if len(flat) != len({str(p['playerId']) for p in flat}) or {str(p['playerId']) for p in flat} != verified:
                raise ValueError('Raw dressed roster/box identity mismatch')
            starters = {str(p['playerId']) for p in stats['goalies'] if p.get('starter') is True}
            if len(starters) != 1 or starters != bold_goalies:
                raise ValueError('Official/raw goalie starter mismatch')
            for p in flat:
                pid = str(p['playerId'])
                raw_ids.add(pid)
                saved_row = saved.get(pid)
                if saved_row is None or saved_row['team_abbrev'] != team['abbrev']:
                    raise ValueError('Raw player absent or different team in saved box')
                fields = [('toi', 'toi')]
                kind = 'goalie' if p['position'] == 'G' else 'skater'
                if kind == 'goalie':
                    fields += [('saves', 'saves'), ('shots_against', 'shotsAgainst'), ('goals_against', 'goalsAgainst')]
                    if saved_row['starter'].lower() != str(p['starter']).lower():
                        raise ValueError('Saved/raw goalie starter mismatch')
                else:
                    fields += [('goals', 'goals'), ('assists', 'assists'), ('shots_on_goal', 'sog'), ('hits', 'hits'), ('shifts', 'shifts')]
                if any(str(saved_row[a]) != str(p[b]) for a, b in fields):
                    raise ValueError('Saved/raw box field mismatch')
                record = exposure(saved_row, kind)
                ledger.append({'game_id': game_id, 'id': pid, 'team': team['abbrev'], 'kind': kind,
                               'listed_status': 'dressed', **record})
            scratches = raw['right_rail_raw']['gameInfo'][side+'Team']['scratches']
            keyed = {name_key(p['firstName']['default']+' '+p['lastName']['default']): p for p in scratches}
            official = report[side+'_scratches']
            if len(keyed) != len(scratches) or len(official) != len(scratches):
                raise ValueError('Scratch count or name ambiguity')
            matched = set()
            for r in official:
                p = keyed.get(name_key(r['name']))
                if p is None:
                    aliases = [p for p in scratches if reviewed.get((game_id, team['abbrev'], str(p['id']))) == name_key(r['name'])]
                    if len(aliases) == 1:
                        p = aliases[0]
                if p is None:
                    raise ValueError('Official/raw scratch identity mismatch')
                pid = str(p['id'])
                if pid in raw_ids or pid in ids or pid in all_scratch_ids:
                    raise ValueError('Duplicate or dressed scratch identity')
                matched.add(pid)
                all_scratch_ids.add(pid)
                ledger.append({'game_id': game_id, 'id': pid, 'team': team['abbrev'],
                               'kind': 'goalie' if r['position'] == 'G' else 'skater',
                               'listed_status': 'scratched', 'appeared': False, 'started': False,
                               'toi_seconds': 0, 'role': 'scratch', 'absence_reason': None})
            if len(matched) != len(scratches):
                raise ValueError('Duplicate official scratch identity')
        if raw_ids != set(ids):
            raise ValueError('Raw roster has an unknown team or unmatched player')
        if raw_ids != set(saved):
            raise ValueError('Saved/raw whole-game player set differs')
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    if errors:
        ledger = []
    for r in ledger:
        r.update(game_date=schedule['game_date'], game_start=schedule['game_time'],
                 pregame_available_at=None, use='historical_outcome_only')
    return {'game_id': game_id, 'status': 'excluded' if errors else 'verified', 'errors': errors,
            'roles': dict(Counter(r['role'] for r in ledger)), 'records': len(ledger),
            'scoring_target_exclusions': sum(bool(r.get('stat_conflicts')) for r in ledger)}, ledger


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--pilot-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--identity-reviews', type=Path)
    a = p.parse_args()
    selection = json.loads((a.pilot_dir / 'selection.json').read_text())
    year = selection['ending_year']
    for path, expected in selection['inputs_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('Selection input changed')
    for kind in ('nhl_schedule', 'skater_box', 'goalie_box'):
        path = a.directory / f'{kind}_{year}.csv'
        if str(path) not in selection['inputs_sha256']:
            raise ValueError('Validator directory differs from selection sources')
    def read(kind):
        with (a.directory / f'{kind}_{year}.csv').open() as stream:
            return list(csv.DictReader(stream))
    schedules = {r['game_id']: r for r in read('nhl_schedule')}
    rows = read('skater_box') + read('goalie_box')
    reviews = json.loads(a.identity_reviews.read_text()) if a.identity_reviews else []
    for review in reviews:
        for path, expected in review['evidence_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ValueError('Identity review source changed')
    a.output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    with (a.output_dir / 'participation-outcomes.jsonl').open('x') as out:
        for case in selection['selection']:
            gid = case['game_id']
            try:
                sources = {}
                receipts = {}
                for suffix in ('json', 'html'):
                    path = a.pilot_dir / f'{gid}.{suffix}'
                    raw = path.read_bytes()
                    receipt = json.loads(path.with_suffix(path.suffix+'.receipt.json').read_text())
                    if hashlib.sha256(raw).hexdigest() != receipt['sha256']:
                        raise ValueError('Source receipt mismatch')
                    sources[suffix] = raw
                    receipts[suffix] = receipt
                result, ledger = validate_game(json.loads(sources['json']), sources['html'].decode('utf-8'),
                                               [r for r in rows if r['game_id'] == gid], gid, schedules[gid], reviews)
                for r in ledger:
                    r['sources'] = receipts
                    out.write(json.dumps(r) + '\n')
            except (OSError, ValueError) as e:
                result = {'game_id': gid, 'status': 'excluded', 'errors': [str(e)], 'records': 0, 'roles': {}}
            result['selection_reason'] = case['reason']
            results.append(result)
    report = {'games': results, 'verified_games': sum(r['status'] == 'verified' for r in results),
              'selection_sha256': hashlib.sha256((a.pilot_dir / 'selection.json').read_bytes()).hexdigest(),
              'records': sum(r['records'] for r in results),
              'expansion_ready': all(r['status'] == 'verified' for r in results),
              'identity_review_sha256': hashlib.sha256(a.identity_reviews.read_bytes()).hexdigest() if a.identity_reviews else None,
              'limitations': ['Post-game cohort is not pregame team membership or a prediction-time player list.',
                              'Scratches have verified source IDs but no inferred injury reason.',
                              'Cross-source agreement is reconciliation, not statistical independence.',
                              'Conflicting scoring statistics do not invalidate independently supported positive ice time; affected scoring targets remain excluded.',
                              'No forecast accuracy, model promotion or current player status established.']}
    (a.output_dir / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
