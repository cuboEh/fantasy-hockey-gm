from copy import deepcopy
import unittest
from archive.tg.personal.experiments.audit_draft_study import audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.study={'evaluation_season':2025,'warnings':[], 'evaluation':{'runs':[
            {'teams':12,'seat':1,'seed':0,
             'result':{'pick_outcomes':[{'id':'1','actual_points':None}]},
             'benchmark':{'pick_outcomes':[{'id':'2','actual_points':100}]}}]}}
        self.corrections={'target':2025,'players':{'1':{'games':0,'points':0,
            'source':'https://example.test/verified','reason':'Confirmed absence','verified_at':'2026-09-10'}}}

    def test_verified_zero_restores_pair_without_mutating_original(self):
        original=deepcopy(self.study)
        result=audit(self.study,self.corrections)
        self.assertEqual(result['complete_pairs'],1)
        self.assertEqual(result['mean_paired_delta'],-100)
        self.assertEqual(self.study,original)

    def test_unverified_missing_remains_missing(self):
        result=audit(self.study,{'target':2025,'players':{}})
        self.assertEqual(result['complete_pairs'],0)
        self.assertIsNone(result['mean_paired_delta'])

    def test_wrong_season_and_invalid_zero_fail(self):
        self.corrections['target']=2024
        with self.assertRaises(ValueError):audit(self.study,self.corrections)
        self.corrections['target']=2025
        self.corrections['players']['1']['points']=5
        with self.assertRaises(ValueError):audit(self.study,self.corrections)
