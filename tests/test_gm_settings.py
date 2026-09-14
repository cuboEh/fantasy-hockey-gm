from copy import deepcopy
from datetime import timedelta
import unittest

from fantasy_hockey.gm_settings import league_snapshot, normalize_settings, settings_component
from fantasy_hockey.gm_state import inspect_snapshot, validate_snapshot
from test_gm import NOW, snapshot


def supplied_config():
    config = deepcopy(snapshot()['inputs']['settings']['data']['config'])
    config['league'].update(max_teams=8, draft_time_display='Example draft time',
                            publicly_viewable=False, custom_notice='Retain this')
    config['rules'] = {
        'max_acquisitions_per_week': 5, 'min_goalie_appearances_per_week': 2,
        'deadline': 'daily-today', 'lock_benched_players': False,
        'allow_direct_injury_slot_adds': True, 'waiver_type': 'continual_rolling_list',
        'waiver_wait_days': 1, 'waiver_mode': 'standard', 'season_trades_unlimited': True,
        'votes_required_to_veto': 3, 'trade_end_date': '2027-02-15',
        'playoff_weeks': [20, 21], 'playoff_reseeding': True,
        'experimental_rule': {'detail': 7},
    }
    return config


def supplied_league():
    return {'teams': 2, 'slot': 1, 'revision': 10,
            'team_names': {'1': 'Example One', '2': 'Example Two'},
            'board': {'players': [
                {'id': f'example:{i}', 'name': f'Example Player {i}', 'team': 'AAA', 'positions': ['C']}
                for i in range(1, 8)]},
            'picks': [{'pick': i, 'team': (i-1) % 2 + 1, 'player_id': f'example:{i}'} for i in range(1, 7)]}


class SettingsTests(unittest.TestCase):
    def component(self):
        return settings_component(supplied_config(), source='Fictional supplied settings',
                                  observed_at=(NOW-timedelta(hours=1)).isoformat())

    def normalized(self, league=None):
        return league_snapshot(league or supplied_league(), self.component(), league_id='local:example',
                               source='Fictional completed-draft snapshot',
                               observed_at=(NOW-timedelta(hours=1)).isoformat(), now=NOW)

    def test_preserves_all_rules_and_distinguishes_capacity_from_participation(self):
        result = normalize_settings(supplied_config())
        self.assertEqual(result['rules']['goalie_minimum'], 2)
        self.assertEqual(result['rules']['lineup_lock'], 'daily_today')
        self.assertEqual(result['rules']['playoff_weeks'], [20, 21])
        self.assertFalse(result['rules']['lock_benched_players'])
        self.assertIsNone(result['rules']['acquisitions_used'])
        self.assertIsNone(result['league_details']['team_count'])
        self.assertEqual(result['league_details']['max_teams'], 8)
        self.assertIsNone(result['timezone'])
        self.assertIsNone(result['matchup'])
        self.assertEqual(result['uninterpreted']['league.custom_notice'], 'Retain this')
        self.assertEqual(result['uninterpreted']['rules.experimental_rule'], {'detail': 7})

    def test_rejects_invalid_typed_rules_and_conflicting_aliases(self):
        mutations = [
            lambda c: c['rules'].update(votes_required_to_veto=True),
            lambda c: c['rules'].update(playoff_weeks=[21, 20]),
            lambda c: c['rules'].update(trade_end_date='2027-02-30'),
            lambda c: c['rules'].update(lock_benched_players='No'),
            lambda c: c['rules'].update(acquisition_limit=5),
            lambda c: c['league'].update(team_count=9),
        ]
        for mutate in mutations:
            config = supplied_config(); mutate(config)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                normalize_settings(config)

    def test_normalizes_full_league_without_inventing_current_lineups_or_free_agents(self):
        result = self.normalized()
        inputs = result['inputs']
        self.assertEqual(inputs['settings']['data']['league_details']['team_count'], 2)
        self.assertEqual(len(inputs['league_rosters']['data']), 2)
        self.assertEqual(len(inputs['roster']['data']), 3)
        self.assertTrue(all(p['selected_position'] is None for p in inputs['roster']['data']))
        remaining = next(p for p in inputs['availability']['data'] if p['id'] == 'example:7')
        self.assertEqual(remaining['state'], 'unknown')
        self.assertIsNone(remaining['owner_team_id'])
        self.assertEqual(inputs['forecasts']['coverage'], 'missing')
        self.assertEqual(result['team']['id'], 'local:example:seat:1')
        self.assertEqual(inputs['league_rosters']['data'][0]['player_names']['example:1'], 'Example Player 1')
        inspected = inspect_snapshot(result, NOW, 1)
        self.assertEqual(inspected['inputs']['roster']['status'], 'freshness_unknown')
        self.assertTrue(any('not interpreted' in issue for issue in inspected['issues']))

    def test_incomplete_or_duplicate_draft_cannot_claim_full_league_coverage(self):
        for kind in ('missing', 'duplicate', 'gap', 'wrong_team', 'missing_name'):
            league = supplied_league()
            if kind == 'missing': league['picks'].pop()
            if kind == 'duplicate': league['picks'][1]['player_id'] = 'example:1'
            if kind == 'gap': league['picks'][-1]['pick'] = 9
            if kind == 'wrong_team': league['picks'][0]['team'] = 9
            if kind == 'missing_name': league['board']['players'][0]['name'] = None
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.normalized(league)

    def test_league_ownership_conflict_rejected_and_legacy_snapshot_still_supported(self):
        validate_snapshot(snapshot(), 'demo-league', 'demo-team', NOW)
        result = self.normalized()
        result['inputs']['league_rosters']['data'][1]['player_ids'].append('example:1')
        with self.assertRaises(ValueError):
            validate_snapshot(result, result['league']['id'], result['team']['id'], NOW)

    def test_reverse_other_team_ownership_must_match_complete_league_rosters(self):
        payload=self.normalized()
        entry=next(r for r in payload['inputs']['availability']['data'] if r['state']=='unknown')
        entry.update(state='owned',owner_team_id=payload['inputs']['league_rosters']['data'][1]['id'])
        with self.assertRaisesRegex(ValueError,'absent from supplied league_rosters'):
            validate_snapshot(payload,payload['league']['id'],payload['team']['id'],NOW)
