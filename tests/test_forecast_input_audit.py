from copy import deepcopy
import unittest

from research.audit_forecast_inputs import audit_history


class ForecastInputAuditTests(unittest.TestCase):
    def setUp(self):
        self.weights = {'skater': {'goals': 5}, 'goalie': {'saves': 1}}
        self.history = {'ending_year': 2026,
                        'games': {str(i): {'id': str(i), 'date': f'2026-01-0{i}', 'teams': ['AAA', 'BBB']}
                                  for i in range(1, 4)},
                        'records': [{'game_id': str(i), 'date': f'2026-01-0{i}', 'id': 'player',
                                     'kind': 'skater', 'team': 'AAA', 'appeared': True, 'stats': {'goals': 0}}
                                    for i in (1, 3)]}

    def test_gap_is_not_a_confirmed_nonappearance_or_zero_target(self):
        before = deepcopy(self.history)
        result = audit_history(self.history, self.weights)
        self.assertEqual(result['unobserved_between_same_team_records'], {'skater': 1})
        self.assertEqual(result['participation_records']['skater'], {'appeared': 2})
        self.assertEqual(result['unscorable_records'], {})
        self.assertFalse(result['independent_holdout_verified'])
        self.assertEqual(self.history, before)

    def test_explicit_false_and_unknown_are_different(self):
        self.history['records'][0]['appeared'] = False
        del self.history['records'][1]['appeared']
        result = audit_history(self.history, self.weights)
        self.assertEqual(result['participation_records']['skater'], {'explicit_nonappearance': 1, 'unknown': 1})

    def test_duplicate_bad_join_and_missing_stat_remain_visible(self):
        self.history['records'].append(deepcopy(self.history['records'][0]))
        self.history['records'][0]['stats'] = {}
        self.history['records'][1]['team'] = 'INVALID'
        result = audit_history(self.history, self.weights)
        self.assertEqual(result['duplicate_player_games'], 1)
        self.assertEqual(result['invalid_game_team_links'], 1)
        self.assertEqual(result['unscorable_records'], {'skater': 1})
        self.assertEqual(result['normalized_feature_records']['expected_goals'], 0)
