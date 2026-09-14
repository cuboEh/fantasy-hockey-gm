"""Fictional, isolated acceptance cases for the P1 GM import foundation."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
import socket
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fantasy_hockey.gm_cli import make_server
from fantasy_hockey.gm_state import INPUTS, canonical, inspect_snapshot, validate_snapshot
from fantasy_hockey import gm_store

NOW = datetime(2026, 9, 14, 18, tzinfo=timezone.utc)


def snapshot(now=NOW):
    def component(data):
        return {'source': 'Fictional acceptance fixture',
                'observed_at': (now-timedelta(minutes=10)).isoformat(),
                'expires_at': (now+timedelta(hours=4)).isoformat(),
                'coverage': 'complete', 'reason': None, 'data': data}
    return {'schema_version': 1, 'data_type': 'illustrative',
            'league': {'id': 'demo-league', 'name': 'Illustrative league'},
            'team': {'id': 'demo-team', 'name': 'Practice roster'},
            'inputs': {
                'settings': component({'config': {'league': {'scoring_type': 'h2h_points'},
                    'roster': {'C': 1, 'G': 1, 'BN': 1},
                    'scoring': {'skater': {'goals': 5, 'shots_on_goal': 0.5},
                                'goalie': {'wins': 4, 'goals_against': -2}}},
                    'timezone': 'America/Edmonton',
                    'matchup': {'start': (now-timedelta(days=1)).date().isoformat(),
                                'end': (now+timedelta(days=5)).date().isoformat()},
                    'rules': {'lineup_lock': 'daily_today', 'acquisition_limit': 4,
                              'acquisitions_used': 1, 'waiver_type': None,
                              'waiver_wait_days': None, 'goalie_minimum': 3,
                              'goalie_qualification': 'active_appearances'}}),
                'roster': component([
                    {'id': 'demo:1', 'name': 'Example Center', 'nhl_team': 'AAA',
                     'positions': ['C'], 'selected_position': 'C'},
                    {'id': 'demo:2', 'name': 'Example Goalie', 'nhl_team': 'BBB',
                     'positions': ['G'], 'selected_position': 'G'}]),
                'availability': component([
                    {'id': 'demo:1', 'state': 'owned', 'owner_team_id': 'demo-team', 'waiver_clears_at': None},
                    {'id': 'demo:2', 'state': 'owned', 'owner_team_id': 'demo-team', 'waiver_clears_at': None},
                    {'id': 'demo:3', 'state': 'waivers', 'owner_team_id': None,
                     'waiver_clears_at': (now+timedelta(hours=2)).isoformat()}]),
                'schedule': component([{'id': 'demo-game', 'teams': ['AAA', 'BBB'],
                                        'starts_at': (now+timedelta(minutes=30)).isoformat()}]),
                'player_status': component([{'id': 'demo:1', 'status': 'unknown', 'confirmed': False}]),
                'forecasts': {'source': 'Not supplied', 'observed_at': None, 'expires_at': None,
                              'coverage': 'missing', 'reason': 'No reviewed in-season forecast', 'data': None}}}


class GmStateTests(unittest.TestCase):
    def validate(self, payload):
        return validate_snapshot(payload, 'demo-league', 'demo-team', NOW)

    def test_inspection_keeps_missing_rules_and_projection_separate(self):
        payload = self.validate(snapshot())
        result = inspect_snapshot(payload, NOW, 1)
        self.assertEqual(result['inputs']['roster']['status'], 'current')
        self.assertEqual(result['inputs']['forecasts']['status'], 'missing')
        self.assertIn('rules: waiver_type is unknown', result['issues'])
        self.assertEqual(result['advice_status'], 'unavailable')
        payload['team']['name'] = 'Changed copy'
        self.assertEqual(snapshot()['team']['name'], 'Practice roster')

    def test_rejects_wrong_identity_duplicates_and_partial_shapes(self):
        cases = []
        for key in ('league', 'team'):
            p = snapshot(); p[key]['id'] = 'wrong'; cases.append(p)
        for key in INPUTS:
            p = snapshot(); p['inputs'][key]['coverage'] = 'partial'; cases.append(p)
        p = snapshot(); p['inputs']['roster']['data'] *= 2; cases.append(p)
        p = snapshot(); p['inputs']['roster']['data'][0]['positions'] = ['C', 'C']; cases.append(p)
        p = snapshot(); p['inputs']['roster']['data'][0]['selected_position'] = 'G'; cases.append(p)
        p = snapshot(); p['inputs']['availability']['data'][0]['state'] = 'free_agent'; cases.append(p)
        p = snapshot(); p['inputs']['settings']['data']['config']['roster']['G'] = 0; cases.append(p)
        p = snapshot(); p['inputs']['settings']['observed_at'] = '2026-09-15T00:00:00Z'; cases.append(p)
        p = snapshot(); p['inputs']['schedule']['data'][0]['starts_at'] = '2026-09-14T20:00:00'; cases.append(p)
        p = snapshot(); p['inputs']['settings']['data']['rules']['acquisitions_used'] = True; cases.append(p)
        cases.extend([None, [], {}, {'schema_version': 1}])
        for payload in cases:
            with self.subTest(payload_type=type(payload).__name__), self.assertRaises(ValueError):
                self.validate(payload)

    def test_expiry_game_and_waiver_boundaries_invalidate_state(self):
        payload = self.validate(snapshot())
        before = inspect_snapshot(payload, NOW, 1)
        same = inspect_snapshot(payload, NOW+timedelta(seconds=1), 1)
        self.assertEqual(before['state_key'], same['state_key'])
        locked = inspect_snapshot(payload, NOW+timedelta(minutes=30), 1)
        self.assertEqual(locked['locked_game_ids'], ['demo-game'])
        self.assertNotEqual(before['state_key'], locked['state_key'])
        waiver = inspect_snapshot(payload, NOW+timedelta(hours=2), 1)
        self.assertNotEqual(locked['state_key'], waiver['state_key'])
        self.assertTrue(any('refresh ownership' in issue for issue in waiver['issues']))
        expired = inspect_snapshot(payload, NOW+timedelta(hours=4), 1)
        self.assertEqual(expired['inputs']['roster']['status'], 'expired')
        self.assertNotEqual(waiver['state_key'], expired['state_key'])

    def test_unknown_freshness_unknown_eligibility_and_unsupported_rule(self):
        payload = snapshot()
        payload['inputs']['roster']['expires_at'] = None
        payload['inputs']['roster']['data'][0]['positions'] = None
        payload['inputs']['settings']['data']['rules']['lineup_lock'] = 'weekly'
        result = inspect_snapshot(self.validate(payload), NOW, 1)
        self.assertEqual(result['inputs']['roster']['status'], 'freshness_unknown')
        self.assertTrue(any('positions is unknown' in issue for issue in result['issues']))
        self.assertTrue(any('not supported' in issue for issue in result['issues']))

    def test_missing_player_coverage_and_reverse_ownership_conflict(self):
        payload = self.validate(snapshot())
        result = inspect_snapshot(payload, NOW, 1)
        self.assertIn('Example Goalie: no player status record supplied', result['issues'])
        self.assertIn('Example Center: participation is unconfirmed', result['issues'])
        payload['inputs']['roster']['data'].pop()
        with self.assertRaisesRegex(ValueError, 'absent roster player'):
            self.validate(payload)

    def test_forecast_inventory_requires_projection_and_dated_version(self):
        payload = snapshot()
        component = deepcopy(payload['inputs']['roster'])
        component['data'] = [{'id': 'demo:1', 'model_version': 'illustrative-v1',
                              'issued_at': component['observed_at'],
                              'horizon_start': NOW.isoformat(),
                              'horizon_end': (NOW+timedelta(days=7)).isoformat(),
                              'data_type': 'projection'}]
        payload['inputs']['forecasts'] = component
        valid = self.validate(payload)
        self.assertNotEqual(inspect_snapshot(snapshot(), NOW, 1)['state_key'],
                            inspect_snapshot(valid, NOW, 1)['state_key'])
        component['data'][0]['data_type'] = 'historical'
        with self.assertRaisesRegex(ValueError, 'historical'):
            self.validate(payload)

    def test_local_day_and_each_input_change_invalidate_advice_identity(self):
        payload = self.validate(snapshot())
        before = inspect_snapshot(payload, NOW, 1)['state_key']
        changes = [
            ('roster', lambda d: d[0].update(name='Corrected player')),
            ('availability', lambda d: d[2].update(state='free_agent', waiver_clears_at=None)),
            ('schedule', lambda d: d[0].update(starts_at=(NOW+timedelta(hours=1)).isoformat())),
            ('settings', lambda d: d['rules'].update(acquisitions_used=2)),
            ('player_status', lambda d: d[0].update(status='injured', confirmed=True))]
        for name, change in changes:
            altered = deepcopy(payload); change(altered['inputs'][name]['data'])
            self.assertNotEqual(before, inspect_snapshot(self.validate(altered), NOW, 1)['state_key'])
        self.assertNotEqual(before, inspect_snapshot(payload, NOW+timedelta(days=1), 1)['state_key'])


class GmStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'gm.sqlite'
        gm_store.initialize(self.path, 'demo-league', 'demo-team')

    def save(self, payload=None, **kwargs):
        return gm_store.import_snapshot(self.path, canonical(payload or snapshot()).encode(), now=NOW, **kwargs)

    def test_failed_import_retains_snapshot_and_persists_error_then_recovers(self):
        original = self.save()
        partial = snapshot(); partial['inputs']['roster']['coverage'] = 'partial'
        with self.assertRaisesRegex(ValueError, 'partial'):
            self.save(partial)
        retained = gm_store.view(self.path, now=NOW)
        self.assertEqual(retained['snapshot'], original['snapshot'])
        self.assertEqual(retained['last_success_at'], original['last_success_at'])
        self.assertEqual(retained['snapshot_status'], 'historical')
        self.assertNotEqual(retained['state_key'], original['state_key'])
        self.assertEqual(retained['revision'], 2)
        recovered = self.save(expected_revision=2)
        self.assertIsNone(recovered['last_error'])
        self.assertEqual(recovered['revision'], 3)

    def test_stale_window_cannot_import_and_invalid_json_is_recorded(self):
        self.save()
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.save(expected_revision=0)
        self.assertEqual(gm_store.view(self.path, now=NOW)['revision'], 1)
        for raw in (b'{', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff'):
            with self.assertRaises(ValueError):
                gm_store.import_snapshot(self.path, raw, now=NOW)
            self.assertIsNotNone(gm_store.view(self.path, now=NOW)['last_error'])
        self.assertEqual(gm_store.view(self.path, now=NOW)['snapshot'], snapshot())

    def test_cannot_replace_supplied_inputs_with_missing_or_older_data(self):
        self.save()
        p = snapshot(); p['inputs']['roster'] = deepcopy(p['inputs']['forecasts'])
        with self.assertRaisesRegex(ValueError, 'incomplete refresh'):
            self.save(p)
        p = snapshot(); p['inputs']['roster']['observed_at'] = (NOW-timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, 'older'):
            self.save(p)
        self.assertEqual(gm_store.view(self.path, now=NOW)['snapshot'], snapshot())

    def test_no_overwrite_no_draft_mutation_and_rollback_on_interrupt(self):
        with self.assertRaises(FileExistsError):
            gm_store.initialize(self.path, 'another', 'team')
        other = Path(self.tmp.name)/'draft.sqlite'
        with sqlite3.connect(other) as db:
            db.execute('CREATE TABLE picks (id INTEGER)')
        original = other.read_bytes()
        with self.assertRaisesRegex(ValueError, 'not a GM workspace'):
            gm_store.import_snapshot(other, canonical(snapshot()).encode(), now=NOW)
        self.assertEqual(original, other.read_bytes())
        self.save()
        with self.assertRaises(RuntimeError):
            with gm_store.connect(self.path) as db:
                db.execute('INSERT INTO imports(at,error) VALUES (?,?)', (NOW.isoformat(), 'interrupted'))
                raise RuntimeError('simulated interruption')
        self.assertEqual(gm_store.view(self.path, now=NOW)['revision'], 1)

    def test_unfinished_attempt_survives_reopen_and_recovery(self):
        saved = self.save()
        attempt = gm_store.begin_import(self.path, now=NOW, expected_revision=1)
        pending = gm_store.view(self.path, now=NOW)
        self.assertEqual(pending['snapshot'], saved['snapshot'])
        self.assertEqual(pending['last_error'], gm_store.PENDING)
        self.assertNotEqual(saved['state_key'], pending['state_key'])
        self.assertEqual(pending['inputs']['roster']['last_refresh_error'], gm_store.PENDING)
        gm_store.complete_import(self.path, attempt, canonical(snapshot()).encode(), now=NOW)
        self.assertIsNone(gm_store.view(self.path, now=NOW)['last_error'])

    def test_superseded_completion_cannot_overwrite_newer_import(self):
        self.save()
        attempt = gm_store.begin_import(self.path, now=NOW)
        changed = snapshot(); changed['inputs']['settings']['data']['rules']['acquisitions_used'] = 2
        newer = self.save(changed)
        with self.assertRaisesRegex(ValueError, 'superseded'):
            gm_store.complete_import(self.path, attempt, canonical(snapshot()).encode(), now=NOW)
        gm_store.fail_import(self.path, attempt, 'Late failure', now=NOW)
        current = gm_store.view(self.path, now=NOW)
        self.assertEqual(current['snapshot'], newer['snapshot'])
        self.assertIsNone(current['last_error'])

    def test_unreadable_file_attempt_is_recorded_without_losing_data(self):
        before = self.save()
        with self.assertRaises(FileNotFoundError):
            gm_store.import_file(self.path, self.path.parent/'missing.json', now=NOW)
        after = gm_store.view(self.path, now=NOW)
        self.assertEqual(before['snapshot'], after['snapshot'])
        self.assertIn('Cannot read', after['last_error'])


class GmHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'gm.sqlite'
        gm_store.initialize(self.path, 'demo-league', 'demo-team')
        self.server = make_server(self.path, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.addCleanup(self.stop)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        with urlopen(self.url) as response:
            self.token = re.search("const token='([^']+)'", response.read().decode()).group(1)

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def test_import_inspection_security_and_failure_recovery(self):
        raw = canonical(snapshot(gm_store.utc_now())).encode()
        headers = {'Content-Type': 'application/json', 'X-GM-Token': self.token, 'X-GM-Revision': '0'}
        with self.assertRaises(HTTPError):
            urlopen(Request(self.url+'/api/import', data=raw))
        with self.assertRaises(HTTPError):
            urlopen(Request(self.url+'/api/state', headers={'Host': 'other.example'}))
        with urlopen(Request(self.url+'/api/import', data=raw, headers=headers)) as response:
            result = json.load(response)
        self.assertEqual(result['snapshot']['team']['id'], 'demo-team')
        self.assertEqual(result['revision'], 1)
        headers['X-GM-Revision'] = '1'
        with self.assertRaises(HTTPError):
            urlopen(Request(self.url+'/api/import', data=b'{', headers=headers))
        with urlopen(self.url+'/api/state') as response:
            retained = json.load(response)
        self.assertEqual(retained['snapshot'], result['snapshot'])
        self.assertIsNotNone(retained['last_error'])

    def test_truncated_transport_records_failure_and_recovers(self):
        raw = canonical(snapshot(gm_store.utc_now())).encode()
        gm_store.import_snapshot(self.path, raw)
        headers = (f'POST /api/import HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n'
                   f'Content-Type: application/json\r\nX-GM-Token: {self.token}\r\n'
                   'X-GM-Revision: 1\r\nContent-Length: 100\r\n\r\n{')
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=3) as client:
            client.sendall(headers.encode()); client.shutdown(socket.SHUT_WR)
            self.assertIn(b'400', client.recv(4096))
        retained = gm_store.view(self.path)
        self.assertIn('before the complete snapshot', retained['last_error'])
        self.assertEqual(len(retained['snapshot']['inputs']['roster']['data']), 2)
        self.assertIsNone(gm_store.import_snapshot(self.path, raw)['last_error'])

    def test_state_refresh_supplies_current_session_token_without_reloading_page(self):
        with urlopen(self.url+'/api/state') as response:
            refreshed_token = response.headers['X-GM-Token']
        self.assertEqual(refreshed_token, self.token)
        raw = canonical(snapshot(gm_store.utc_now())).encode()
        request = Request(self.url+'/api/import', data=raw, headers={
            'Content-Type': 'application/json', 'X-GM-Token': refreshed_token, 'X-GM-Revision': '0'})
        with urlopen(request) as response:
            self.assertEqual(json.load(response)['revision'], 1)


if __name__ == '__main__':
    unittest.main()
