from copy import deepcopy
import unittest

from research.audit_participation_records import audit_season, exposure


class ParticipationRecordsTests(unittest.TestCase):
    def goalie(self, **changes):
        return dict(toi='00:00', starter='false', saves='0', shots_against='0',
                    goals_against='0', decision='', **changes)

    def test_unused_backup_and_relief_are_distinct(self):
        row = self.goalie()
        self.assertFalse(exposure(row, 'goalie')['appeared'])
        row.update(toi='02:13', saves='2', shots_against='2')
        result = exposure(row, 'goalie')
        self.assertEqual(result['toi_seconds'], 133)
        self.assertEqual(result['role'], 'relief')
        self.assertFalse(result['started'])

    def test_scoring_conflict_does_not_erase_positive_ice_time(self):
        row = self.goalie()
        row.update(toi='20:00', starter='TRUE', saves='10', goals_against='1', shots_against='12')
        result = exposure(row, 'goalie')
        self.assertTrue(result['appeared'])
        self.assertTrue(result['started'])
        self.assertTrue(result['stat_conflicts'])

    def test_contradictory_or_missing_records_not_zero_filled(self):
        for changes in ({'starter': ''}, {'starter': 'true'}, {'saves': '1'},
                        {'toi': '01:60'}, {'toi': '-1:00'}, {'decision': 'W'}):
            row = self.goalie()
            row.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                exposure(row, 'goalie')

    def tables(self):
        tables = {k: [] for k in ('nhl_schedule', 'skater_box', 'goalie_box', 'player_box', 'team_box')}
        tables['nhl_schedule'] = [dict(game_id='2025020001', season_full='20252026', game_type='R',
                                      game_state='OFF', game_date='2025-10-01', game_time='2025-10-01T23:00:00Z',
                                      home_team_abbr='AAA', away_team_abbr='BBB')]
        for side, team in [('home', 'AAA'), ('away', 'BBB')]:
            base = dict(game_id='2025020001', season='20252026', game_date='2025-10-01',
                        home_away=side, team_abbrev=team)
            skater = dict(base, player_id=team+'1', toi='12:30', goals='0', assists='0',
                          shots_on_goal='0', hits='0', shifts='12')
            goalie = dict(base, player_id=team+'2', **self.goalie())
            goalie.update(toi='60:00', starter='true')
            tables['skater_box'].append(skater)
            tables['goalie_box'].append(goalie)
            tables['player_box'].extend([deepcopy(skater), deepcopy(goalie)])
            tables['team_box'].append(dict(base, goals='0', shots_on_goal='0', hits='0'))
        return tables

    def test_clean_join_does_not_create_missing_player_outcomes(self):
        tables = self.tables()
        before = deepcopy(tables)
        report, rows = audit_season(tables, 2026)
        self.assertEqual(report['issues'], {})
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['pregame_available_at'] is None for r in rows))
        self.assertEqual(tables, before)

    def test_wrong_season_combined_release_cannot_supply_membership(self):
        tables = self.tables()
        for row in tables['player_box']:
            row['season'] = '20242025'
        report, rows = audit_season(tables, 2026)
        self.assertEqual(report['issues']['player_box_wrong_season'], 4)
        self.assertEqual(report['issues']['dedicated_missing_in_combined'], 4)
        self.assertEqual(len(rows), 4)

    def test_duplicate_identity_and_bad_team_are_excluded(self):
        tables = self.tables()
        tables['skater_box'].append(deepcopy(tables['skater_box'][0]))
        tables['goalie_box'][0]['team_abbrev'] = 'XXX'
        report, rows = audit_season(tables, 2026)
        self.assertEqual(report['issues']['duplicate_dedicated_player_game'], 1)
        self.assertEqual(report['issues']['invalid_player_team_link'], 1)
        self.assertEqual(len(rows), 2)

    def test_legacy_rows_without_game_identity_are_not_positionally_joined(self):
        tables = self.tables()
        for row in tables['player_box']:
            del row['game_id']
        report, rows = audit_season(tables, 2026)
        self.assertEqual(report['issues']['player_box_missing_identity_columns'], 4)
        self.assertEqual(report['issues']['dedicated_missing_in_combined'], 4)
        self.assertEqual(len(rows), 4)


if __name__ == '__main__':
    unittest.main()
