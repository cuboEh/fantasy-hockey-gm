from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research.fetch_participation_pilot import cache_source
from research.validate_participation_pilot import parse_report, validate_game


class ParticipationPilotTests(unittest.TestCase):
    def fixture(self):
        schedule = {'season_full': '20252026', 'game_date': '2025-10-01', 'game_time': '2025-10-01T23:00:00Z',
                    'home_team_abbr': 'AAA', 'away_team_abbr': 'BBB'}
        box = {'id': 2025020001, 'season': 20252026, 'gameDate': '2025-10-01',
               'gameState': 'OFF', 'gameType': 2, 'playerByGameStats': {}}
        raw = {'boxscore_raw': box, 'pbp_raw': {'id': 2025020001, 'rosterSpots': []},
               'right_rail_raw': {'gameInfo': {}}}
        saved, blocks, scratch_blocks = [], [], []
        for team_id, side, team in [(1, 'away', 'BBB'), (2, 'home', 'AAA')]:
            box[side+'Team'] = {'id': team_id, 'abbrev': team}
            players = []
            report_rows = []
            for n, pos, name in [(1, 'C', 'Skater'), (2, 'G', 'Starter'), (3, 'G', 'Backup')]:
                pid = team_id * 100 + n
                first = 'Alpha' if team_id == 1 else 'Beta'
                raw['pbp_raw']['rosterSpots'].append(dict(teamId=team_id, playerId=pid, sweaterNumber=n,
                                                        positionCode=pos, firstName={'default': first}, lastName={'default': name}))
                p = dict(playerId=pid, position=pos, toi='00:00' if n == 3 else '12:00')
                r = dict(player_id=str(pid), team_abbrev=team, toi=p['toi'])
                if pos == 'G':
                    p.update(starter=n == 2, saves=0, shotsAgainst=0, goalsAgainst=0)
                    r.update(starter=str(n == 2).lower(), saves='0', shots_against='0', goals_against='0', decision='')
                else:
                    p.update(goals=0, assists=0, sog=0, hits=0, shifts=10)
                    r.update(goals='0', assists='0', shots_on_goal='0', hits='0', shifts='10')
                players.append(p)
                saved.append(r)
                css = 'bold' if n == 2 else ''
                report_rows.append(f'<tr><td class="{css}">{n}</td><td>{pos}</td><td>{first} {name}</td></tr>')
            box['playerByGameStats'][side+'Team'] = {'forwards': players[:1], 'defense': [], 'goalies': players[1:]}
            raw['right_rail_raw']['gameInfo'][side+'Team'] = {'scratches': [dict(id=team_id*100+4,
                firstName={'default': first}, lastName={'default': 'Scratch'})]}
            blocks.append(''.join(report_rows))
            scratch_blocks.append(f'<tr><td>4</td><td>D</td><td>{first} Scratch</td></tr>')
        header = '<tr><td>#</td><td>Pos</td><td>Name</td></tr>'
        html = 'Game 0001 October 1, 2025 Final' + ''.join('<table>'+header+b+'</table>' for b in blocks+scratch_blocks)
        return raw, html, saved, schedule

    def validate(self, raw, html, saved, schedule):
        return validate_game(raw, html, saved, '2025020001', schedule)

    def test_reconciles_dressed_unused_and_scratched_without_pregame_claim(self):
        fixture = self.fixture()
        before = deepcopy(fixture)
        result, rows = self.validate(*fixture)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['roles']['scratch'], 2)
        self.assertEqual(result['roles']['unused_listed_goalie'], 2)
        self.assertTrue(all(r['pregame_available_at'] is None for r in rows))
        self.assertEqual(fixture, before)

    def test_wrong_game_date_or_missing_table_rejected(self):
        _, html, _, _ = self.fixture()
        for changed in (html.replace('0001', '0002'), html.replace('October 1', 'October 2'), html.replace('#', 'Number', 1)):
            with self.assertRaises(ValueError):
                parse_report(changed, '2025020001', '2025-10-01')

    def test_explicit_empty_scratch_side_does_not_shift_home_and_away(self):
        _, html, _, _ = self.fixture()
        tables = html.split('<table>')[1:]
        dressed = ''.join('<table>'+t for t in tables[:2])
        home_scratches = '<table>'+tables[3]
        report = ('Game 0001 October 1, 2025 Final'+dressed+
                  '<table><tr id="Scratches"><td><table><tr><td>&nbsp;</td></tr></table></td>'+
                  '<td>'+home_scratches+'</td></tr></table>')
        parsed = parse_report(report, '2025020001', '2025-10-01')
        self.assertEqual(parsed['away_scratches'], [])
        self.assertEqual(parsed['home_scratches'][0]['name'], 'Beta Scratch')
        with self.assertRaises(ValueError):
            parse_report(report.replace('&nbsp;', 'Unavailable'), '2025020001', '2025-10-01')

    def test_jersey_alone_cannot_establish_identity(self):
        raw, html, saved, schedule = self.fixture()
        result, rows = self.validate(raw, html.replace('Alpha Skater', 'Different Person'), saved, schedule)
        self.assertEqual(result['status'], 'excluded')
        self.assertEqual(rows, [])

    def test_explicit_alias_review_is_scoped_to_game_team_and_player(self):
        raw, html, saved, schedule = self.fixture()
        html = html.replace('Alpha Skater', 'Alphonso Skater')
        review = {'game_id': '2025020001', 'team': 'BBB', 'id': '101', 'report_name': 'Alphonso Skater'}
        result, rows = validate_game(raw, html, saved, '2025020001', schedule, [review])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(len(rows), 8)
        for field, value in [('team', 'AAA'), ('game_id', '2025020002'), ('id', '201')]:
            changed = dict(review, **{field: value})
            result, rows = validate_game(raw, html, saved, '2025020001', schedule, [changed])
            self.assertEqual(result['status'], 'excluded')
            self.assertEqual(rows, [])

    def test_scratch_cannot_also_be_dressed(self):
        raw, html, saved, schedule = self.fixture()
        raw['right_rail_raw']['gameInfo']['awayTeam']['scratches'][0]['id'] = 101
        result, rows = self.validate(raw, html, saved, schedule)
        self.assertEqual(result['status'], 'excluded')
        self.assertEqual(rows, [])

    def test_disagreement_or_missing_player_excludes_entire_game(self):
        for mode in ('missing', 'stats', 'starter', 'duplicate', 'unknown_team'):
            raw, html, saved, schedule = self.fixture()
            if mode == 'missing':
                saved.pop()
            elif mode == 'stats':
                saved[0]['hits'] = '1'
            elif mode == 'starter':
                saved[1]['starter'] = 'false'
            elif mode == 'duplicate':
                saved.append(deepcopy(saved[0]))
            else:
                raw['pbp_raw']['rosterSpots'].append(dict(raw['pbp_raw']['rosterSpots'][0], playerId=999, teamId=999))
            result, rows = self.validate(raw, html, saved, schedule)
            with self.subTest(mode=mode):
                self.assertEqual(result['status'], 'excluded')
                self.assertEqual(rows, [])

    def test_cached_source_tampering_is_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'game.json'
            p.write_text('{}')
            receipt = {'url': 'https://example.invalid/game', 'sha256': hashlib.sha256(b'{}').hexdigest()}
            p.with_suffix('.json.receipt.json').write_text(json.dumps(receipt))
            self.assertEqual(cache_source(p, receipt['url']), receipt)
            p.write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                cache_source(p, receipt['url'])


if __name__ == '__main__':
    unittest.main()
