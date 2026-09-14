from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fantasy_hockey import gm_store
from fantasy_hockey.gm_state import canonical
from test_gm import NOW
from test_gm_advice import decision_snapshot


class DecisionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'gm.sqlite'
        gm_store.initialize(self.path,'demo-league','demo-team')
        self.payload=decision_snapshot()
        gm_store.import_snapshot(self.path,canonical(self.payload).encode(),now=NOW)

    def test_saved_comparison_persists_and_is_retired_after_ownership_import(self):
        state=gm_store.view(self.path,now=NOW)
        saved=gm_store.save_decision(self.path,'pickup',{'candidate_id':'pickup','drop_id':'center'},state['state_key'],now=NOW)
        self.assertEqual(saved['result']['net_points'],27)
        self.assertFalse(gm_store.view(self.path,now=NOW)['saved_decisions'][0]['historical'])
        p=deepcopy(self.payload)
        p['inputs']['settings']['data']['rules']['acquisitions_used']=2
        gm_store.import_snapshot(self.path,canonical(p).encode(),now=NOW)
        self.assertTrue(gm_store.view(self.path,now=NOW)['saved_decisions'][0]['historical'])
        with self.assertRaisesRegex(ValueError,'changed'):
            gm_store.save_decision(self.path,'lineup',{},state['state_key'],now=NOW)

    def test_clock_boundary_retires_saved_review(self):
        state=gm_store.view(self.path,now=NOW)
        gm_store.save_decision(self.path,'lineup',{},state['state_key'],now=NOW)
        after=gm_store.view(self.path,now=NOW+timedelta(hours=2))
        self.assertTrue(after['saved_decisions'][0]['historical'])

    def test_calculation_failure_leaves_research_and_retry_available(self):
        with patch('fantasy_hockey.gm_advice.lineups',side_effect=RuntimeError('injected')):
            state=gm_store.view(self.path,now=NOW)
        self.assertEqual(state['lineups']['status'],'error')
        self.assertEqual(len(state['snapshot']['inputs']['roster']['data']),4)
        self.assertEqual(gm_store.view(self.path,now=NOW)['lineups']['status'],'supported')

    def test_interrupted_refresh_restricts_decision_without_losing_snapshot(self):
        gm_store.begin_import(self.path,now=NOW)
        state=gm_store.view(self.path,now=NOW)
        self.assertEqual(state['lineups']['status'],'restricted')
        self.assertIsNotNone(state['snapshot'])

    def test_expired_read_authorization_retains_payload_and_retires_advice(self):
        before=gm_store.view(self.path,now=NOW)
        gm_store.save_decision(self.path,'lineup',{},before['state_key'],now=NOW)
        with self.assertRaisesRegex(ValueError,'authorization'):
            gm_store.refresh_from_reader(self.path,lambda:(_ for _ in ()).throw(PermissionError('private-token-must-not-leak')),now=NOW)
        after=gm_store.view(self.path,now=NOW)
        self.assertEqual(after['snapshot'],before['snapshot'])
        self.assertNotIn('private-token',after['last_error'])
        self.assertEqual(after['lineups']['status'],'restricted')
        self.assertTrue(after['saved_decisions'][0]['historical'])
        gm_store.refresh_from_reader(self.path,lambda:canonical(self.payload).encode(),now=NOW)
        self.assertIsNone(gm_store.view(self.path,now=NOW)['last_error'])

    def test_forecast_change_has_before_after_input_explanation(self):
        p=deepcopy(self.payload)
        p['inputs']['forecasts']['data'][0]['rates']['goals']=0.6
        gm_store.import_snapshot(self.path,canonical(p).encode(),now=NOW)
        changes=gm_store.view(self.path,now=NOW)['forecast_changes']
        self.assertEqual(len(changes),1)
        self.assertIn('rates',changes[0]['fields'])
        self.assertEqual(changes[0]['before']['rates']['goals'],0.4)
        self.assertEqual(changes[0]['after']['rates']['goals'],0.6)
