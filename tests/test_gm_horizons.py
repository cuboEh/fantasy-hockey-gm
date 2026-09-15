from collections import defaultdict
from copy import deepcopy
from datetime import date
import unittest

from fantasy_hockey.gm_forecasts import RateHistory
from research.evaluate_gm_horizons import evaluate, forecast_window, prepare, utc_day


class HorizonEvaluationTests(unittest.TestCase):
    weights = {'skater': {'goals': 6}, 'goalie': {'saves': 0.6}}

    def fixture(self):
        specifications = [('past1', '2025-10-30', ['AAA', 'CCC']),
                          ('past2', '2025-10-31', ['AAA', 'CCC']),
                          ('a1', '2025-11-03', ['AAA', 'CCC']),
                          ('b1', '2025-11-03', ['BBB', 'DDD']),
                          ('a2', '2025-11-05', ['AAA', 'CCC'])]
        games = {gid: {'id': gid, 'date': day, 'start': day+'T18:00:00Z', 'teams': teams}
                 for gid, day, teams in specifications}
        scoring, exposure = [], []

        def add(gid, pid, team, appeared, goals, kind='skater'):
            g = games[gid]
            stats = {'goals': goals} if kind == 'skater' else {'saves': goals}
            scoring.append({'game_id': gid, 'id': pid, 'team': team, 'kind': kind,
                            'date': g['date'], 'appeared': appeared, 'stats': stats, 'points': -999})
            exposure.append({'game_id': gid, 'id': pid, 'team': team, 'kind': kind,
                             'game_start': g['start'], 'appeared': appeared, 'stat_conflicts': []})
        add('past1', 'p', 'AAA', True, 2)
        add('past2', 'p', 'AAA', False, 0)
        add('b1', 'p', 'BBB', True, 3)
        add('b1', 'new', 'BBB', True, 1)
        return [{'games': games, 'records': scoring, 'source_conflicts': []}], exposure, set(games)

    def run_fixture(self, histories=None, exposure=None, verified=None, end='2025-11-10', max_cases=300000):
        if histories is None:
            histories, exposure, verified = self.fixture()
        ledger = []
        report = evaluate(histories, exposure, verified, self.weights, '2025-11-03', end,
                          ledger.append, max_cases=max_cases)
        return report, ledger

    def test_daily_and_frozen_weekly_hand_calculation_includes_team_change(self):
        report, rows = self.run_fixture()
        first = [r for r in rows if r['forecast']['cutoff'] == '2025-11-03']
        self.assertEqual(len(first), 2)
        daily, weekly = first
        for r in first:
            f, actual = r['forecast'], r['outcome']
            self.assertEqual(f['id'], 'p')
            self.assertEqual(f['last_known_team'], 'AAA')
            self.assertEqual(f['workload_observations'], 2)
            self.assertEqual(f['models']['baseline']['rates'], {'goals': 2.0})
            self.assertEqual(actual['actual_teams'], ['BBB'])
            self.assertEqual(actual['points'], 18.0)  # Recomputed, never stored -999.
        self.assertEqual(daily['forecast']['models']['baseline']['expected_appearances'], 0.5)
        self.assertEqual(daily['forecast']['models']['baseline']['expected_points'], 6.0)
        self.assertEqual(weekly['forecast']['forecast_game_ids'], ['a1', 'a2'])
        self.assertEqual(weekly['forecast']['models']['baseline']['expected_appearances'], 1.0)
        self.assertEqual(weekly['forecast']['models']['baseline']['expected_stats'], {'goals': 2.0})
        self.assertEqual(weekly['forecast']['models']['baseline']['any_appearance_probability'], 0.75)
        self.assertEqual(weekly['forecast']['models']['baseline']['expected_points'], 12.0)
        self.assertEqual(report['metrics']['7d:skater']['metrics']['point_mae']['baseline'], 6.0)
        self.assertEqual(report['coverage']['7d_actual_appearing_player_windows_outside_cohort'], 1)

    def test_future_stats_membership_and_new_player_do_not_change_first_forecasts(self):
        histories, exposure, verified = self.fixture()
        before = deepcopy((histories, exposure, verified))
        _, original = self.run_fixture(histories, exposure, verified)
        self.assertEqual((histories, exposure, verified), before)
        for row in histories[0]['records']:
            if row['game_id'] == 'b1':
                row['stats']['goals'] = 99
                row['team'] = 'DDD'
        for row in exposure:
            if row['game_id'] == 'b1':
                row['team'] = 'DDD'
        # A changed final roster inside the horizon must not enter its cutoff cohort.
        exposure.append(dict(exposure[-1], id='future-only', appeared=False))
        _, changed = self.run_fixture(histories, exposure, verified)
        frozen = lambda rows: [r['forecast'] for r in rows if r['forecast']['cutoff'] == '2025-11-03']
        self.assertEqual(frozen(original), frozen(changed))
        self.assertNotEqual(original[0]['outcome'], changed[0]['outcome'])

    def test_scoring_conflict_keeps_workload_and_excludes_points(self):
        histories, exposure, verified = self.fixture()
        histories[0]['source_conflicts'].append({'game_id': 'b1', 'id': 'p'})
        report, rows = self.run_fixture(histories, exposure, verified, end='2025-11-04')
        self.assertEqual(rows[0]['outcome']['appearances'], 1)
        self.assertIsNone(rows[0]['outcome']['points'])
        self.assertEqual(report['metrics']['1d:skater']['metrics']['appearance_mae']['n'], 1)
        self.assertNotIn('point_mae', report['metrics']['1d:skater']['metrics'])

    def test_missing_game_is_not_a_zero_outcome_even_if_another_team(self):
        histories, exposure, verified = self.fixture()
        verified.remove('b1')
        report, rows = self.run_fixture(histories, exposure, verified, end='2025-11-04')
        self.assertIsNone(rows[0]['outcome'])
        self.assertEqual(report['coverage']['1d_missing_coverage_windows'], 1)
        self.assertEqual(report['metrics'], {})
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.run_fixture(histories, exposure, verified, end='2025-11-04', max_cases=0)

    def test_complete_coverage_can_establish_absence_of_preselected_player(self):
        histories, exposure, verified = self.fixture()
        exposure = [r for r in exposure if r['game_id'] != 'b1']
        histories[0]['records'] = [r for r in histories[0]['records'] if r['game_id'] != 'b1']
        _, rows = self.run_fixture(histories, exposure, verified, end='2025-11-04')
        self.assertEqual(rows[0]['outcome']['appearances'], 0)
        self.assertEqual(rows[0]['outcome']['points'], 0)

    def test_reporting_lag_and_stale_membership(self):
        h, e, v = self.fixture()
        games, _, _, training, participation = prepare(h, e, v, self.weights)
        engine = RateHistory(self.weights)
        for row in training:
            if row['date'] < '2025-11-02':
                engine.add(row)
        obs = defaultdict(list)
        for row in participation:
            obs[row['id']].append(row)
        cases = forecast_window(engine, obs, games, date(2025, 11, 3), 7)
        self.assertEqual([r['id'] for r in cases], ['p'])
        self.assertEqual(forecast_window(engine, obs, games, date(2025, 12, 10), 1), [])
        bad = RateHistory(self.weights)
        row = dict(training[0], date='2025-11-02')
        bad.add(row)
        with self.assertRaisesRegex(ValueError, 'reporting lag'):
            forecast_window(bad, obs, games, date(2025, 11, 3), 1)

    def test_no_scoring_history_is_unknown_not_zero(self):
        h, e, v = self.fixture()
        e[0].update(id='g', kind='goalie', appeared=False)
        e[1].update(id='g', kind='goalie', appeared=False)
        h[0]['records'] = [r for r in h[0]['records'] if r['game_id'] == 'b1']
        report, rows = self.run_fixture(h, e, v, end='2025-11-04')
        self.assertEqual(rows[0]['forecast']['kind'], 'goalie')
        self.assertEqual(rows[0]['forecast']['models']['baseline']['expected_appearances'], 0.25)
        self.assertIsNone(rows[0]['forecast']['models']['baseline']['expected_points'])
        self.assertEqual(report['metrics']['1d:goalie']['coverage']['scoring_forecast_unsupported'], 1)

    def test_deterministic_paired_report_and_duplicate_rejection(self):
        first, rows = self.run_fixture()
        second, repeated = self.run_fixture()
        self.assertEqual(first, second)
        self.assertEqual(rows, repeated)
        h, e, v = self.fixture()
        e.append(deepcopy(e[0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate participation'):
            self.run_fixture(h, e, v)

    def test_timezone_conversion(self):
        self.assertEqual(utc_day('2025-11-02T21:00:00-07:00'), '2025-11-03')
        with self.assertRaises(ValueError):
            utc_day('2025-11-02T21:00:00')


if __name__ == '__main__':
    unittest.main()
