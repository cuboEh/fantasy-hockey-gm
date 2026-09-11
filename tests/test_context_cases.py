from copy import deepcopy
import unittest
from research.context_cases import validate_cases


class ContextCaseTests(unittest.TestCase):
    def setUp(self):
        self.case={'case_id':'example','player_id':'nhl:1','season':'20242025','cutoff':'2024-09-13',
                   'event_type':'trade','event_date':'2024-06-19','source_date':'2024-06-19',
                   'source':'fixture','fact':'Trade','team_before':'AAA','team_after':'BBB',
                   'expected_role':None,'role_label_kind':'unknown','health_status':None,
                   'projected_starts':None,'selection_note':'Retrospective pilot'}

    def test_future_evidence_and_outcome_fields_rejected(self):
        self.assertEqual(validate_cases([self.case]),[self.case])
        future={**self.case,'source_date':'2024-10-01'}
        with self.assertRaises(ValueError):validate_cases([future])
        with self.assertRaises(ValueError):validate_cases([{**self.case,'observed_starts':50}])

    def test_unknown_role_and_duplicate_cases(self):
        with self.assertRaises(ValueError):validate_cases([{**self.case,'expected_role':'starter'}])
        with self.assertRaises(ValueError):validate_cases([self.case,deepcopy(self.case)])
