from copy import deepcopy
from datetime import date
from decimal import Decimal
import unittest
from archive.tg.personal.experiments.review_workloads import build_review


class WorkloadReviewTests(unittest.TestCase):
    def test_bounds_missing_projection_and_no_mutation(self):
        board={'as_of':'2026-09-10','assumptions':{'season_games':84},'players':[
            {'id':'a','name':'A','team':'AAA','kind':'skater','projected_games':80,'points_per_game':10,'projected_points':800},
            {'id':'b','name':'B','team':'BBB','kind':'skater','projected_games':None,'points_per_game':None,'projected_points':None}]}
        evidence={'players':[{'id':pid,'fact':'Fixture','source':'fixture','evidence_date':'2026-09-09','questions':['Unresolved']} for pid in ('a','b')]}
        original=deepcopy(board)
        report=build_review(board,evidence,date(2026,9,10))
        self.assertEqual(report['rows'][0]['workload_sensitivity'][-1]['points'],Decimal(840))
        self.assertEqual(report['rows'][1]['workload_sensitivity'],[])
        self.assertEqual(board,original)
        evidence['players'][0]['evidence_date']='2026-09-11'
        with self.assertRaises(ValueError):build_review(board,evidence,date(2026,9,10))
