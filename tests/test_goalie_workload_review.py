from copy import deepcopy
from datetime import date
import unittest
from fantasy_hockey.workload_review import validate_review


def fixture():
    return {'review_version':2,'as_of':'2026-09-10','assumptions':['Analyst scenario'],
            'newly_reviewed_ids':['nhl:1'],
            'goalies':[{'id':'nhl:1','name':'Samuel Example','team':'MTL','review_status':'source_reviewed_scenario',
                        'baseline_starts':12,'downside_starts':0,'rate':'5', 'review_by':'2026-09-12',
                        'evidence':{'source':'https://example.org/report','date':'2026-09-09','fact':'Contested backup job'}}],
            'teams':{'MTL':{'starts':{'nhl:1':12},'other_starts':72,
                            'downside_starts':{'nhl:1':0},'downside_other_starts':84}}}


class WorkloadReviewTests(unittest.TestCase):
    def test_id_matching_ignores_name_variants_and_keeps_zero(self):
        data=fixture();data['goalies'][0]['name']='Sam Example'
        self.assertEqual(validate_review(data,date(2026,9,10))['goalies'],1)
        data['teams']['MTL']['starts']={'Sam Example':12}
        with self.assertRaises(ValueError):validate_review(data,date(2026,9,10))

    def test_duplicate_future_and_bad_budget_rejected(self):
        for change in [lambda d:d['goalies'].append(deepcopy(d['goalies'][0])),
                       lambda d:d['goalies'][0]['evidence'].update(date='2026-09-11'),
                       lambda d:d['teams']['MTL'].update(other_starts=84)]:
            with self.subTest(change=change):
                data=fixture();change(data)
                with self.assertRaises(ValueError):validate_review(data,date(2026,9,10))

    def test_unresolved_is_not_zero_or_fake_projection(self):
        data=fixture();g=data['goalies'][0]
        g.update(review_status='reviewed_unresolved',baseline_starts=None,downside_starts=None,rate=None)
        data['teams']['MTL'].update(starts={},other_starts=84,downside_starts={},downside_other_starts=84)
        result=validate_review(data,date(2026,9,10))
        self.assertEqual(result['unresolved_ids'],['nhl:1'])
        g['baseline_starts']=0
        with self.assertRaises(ValueError):validate_review(data,date(2026,9,10))
