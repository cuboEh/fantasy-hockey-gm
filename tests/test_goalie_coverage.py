import unittest
from itertools import product

from fantasy_hockey.backtest import Forecast
from fantasy_hockey.goalie_coverage import qualified_expectation, coverage_evaluator
from fantasy_hockey.seasonlab import opportunity_evaluator


class GoalieCoverageTests(unittest.TestCase):
    def test_joint_reward_matches_enumeration(self):
        events = [(0.2, -3), (0.8, 12), (0.6, 4), (0.4, 8)]
        expected = failure = 0
        for outcomes in product((0, 1), repeat=len(events)):
            probability = 1
            for appeared, (chance, _) in zip(outcomes, events):
                probability *= chance if appeared else 1 - chance
            if sum(outcomes) >= 3:
                expected += probability * sum(a * points for a, (_, points) in zip(outcomes, events))
            else:
                failure += probability
        actual = qualified_expectation(events)
        self.assertAlmostEqual(actual[0], expected)
        self.assertAlmostEqual(actual[1], failure)

    def test_insufficient_and_certain_coverage(self):
        self.assertEqual(qualified_expectation([(1, 7)] * 2), (0, 1))
        self.assertEqual(qualified_expectation([(1, 7)] * 3), (21, 0))

    def test_goalie_protects_existing_points_and_skater_unchanged(self):
        pool = [Forecast('a', 'A', 'G', 'goalie', 10, 82, 820),
                Forecast('b', 'B', 'G', 'goalie', 10, 82, 820),
                Forecast('s', 'S', 'C', 'skater', 10, 82, 820)]
        players = {'a': {'team': 'A'}, 'b': {'team': 'B'}, 's': {'team': 'B'}}
        prior = {'games': {'1': {'date': '2024-01-01', 'teams': ['A']},
                           '2': {'date': '2024-01-02', 'teams': ['A']},
                           '3': {'date': '2024-01-03', 'teams': ['B']}}}
        slots = {'G': 2, 'C': 1}
        utility = coverage_evaluator(pool, players, prior, slots)
        raw = opportunity_evaluator(pool, players, prior, slots)
        self.assertEqual(utility(pool[0], []), raw(pool[0], []))
        self.assertAlmostEqual(utility(pool[1], ['a']), 30)
        self.assertEqual(utility(pool[2], ['a']), raw(pool[2], ['a']))

    def test_same_team_pair_cannot_supply_three_starts_in_two_games(self):
        pool = [Forecast(pid, pid, 'G', 'goalie', 10, 41, 410) for pid in ('a', 'b')]
        players = {pid: {'team': 'A'} for pid in ('a', 'b')}
        prior = {'games': {str(i): {'date': f'2024-01-0{i}', 'teams': ['A']} for i in (1, 2)}}
        utility = coverage_evaluator(pool, players, prior, {'G': 2})
        # No insurance credit from two starts when the minimum is three.
        self.assertEqual(utility(pool[1], ['a']), 10)

    def test_probability_validation(self):
        with self.assertRaises(ValueError):
            qualified_expectation([(1.1, 3)])

    def test_live_board_normalizes_84_game_workloads(self):
        from fantasy_hockey.goalie_coverage import draft_coverage
        players = [{'id': pid, 'name': pid, 'kind': 'goalie', 'team': team,
                    'projected_games': 84, 'points_per_game': 10, 'projected_points': 840}
                   for pid, team in [('a', 'A'), ('b', 'B')]]
        prior = {'games': {'1': {'date': '2024-01-01', 'teams': ['A']},
                           '2': {'date': '2024-01-02', 'teams': ['A']},
                           '3': {'date': '2024-01-03', 'teams': ['B']}}}
        report = draft_coverage(players, {'a'}, {'a'}, prior, {'G': 2}, 84)
        self.assertAlmostEqual(report['candidates'][0]['insurance_points'], 20)
        players[0]['projected_games'] = None
        report = draft_coverage(players, {'a'}, {'a'}, prior, {'G': 2}, 84)
        self.assertFalse(report['available'])
        self.assertEqual(report['candidates'], [])
