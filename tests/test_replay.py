from copy import deepcopy
from decimal import Decimal
import unittest
from fantasy_hockey.replay import Opportunity,select_lineup,plan_days,settle
from fantasy_hockey.backtest import cohort_workload,forecast,Model


def packet():
    return {'schema_version':1,'days':[{'date':'2025-10-01','week':'1',
        'lock_at':'2025-10-01T18:00:00-06:00','available_at':'2025-10-01T12:00:00-06:00',
        'players':[{'id':i,'positions':['C'],'kind':'skater','expected_points':points,
                    'scheduled':True,'available_at':'2025-10-01T12:00:00-06:00','source':'fictional'}
                   for i,points in [('a',10),('b',5)]]}]}


class ReplayTests(unittest.TestCase):
    def test_flexible_position_optimal_assignment(self):
        players=[Opportunity('a','skater',('C','LW'),Decimal(10)),Opportunity('b','skater',('C',),Decimal(9))]
        result=select_lineup(players,{'C':1,'LW':1})
        self.assertEqual(result['assignments'],{'a':'LW','b':'C'})
        self.assertEqual(result['expected_points'],19)

    def test_bench_points_excluded_and_outcome_cannot_change_selection(self):
        decisions=packet();plans=plan_days(decisions,{'C':1,'BN':1})
        actual={'results':[{'date':'2025-10-01','id':i,'appeared':True,'stats':{'goals':goals},'source':'fictional'} for i,goals in [('a',0),('b',5)]]}
        result=settle(plans,actual,{'skater':{'goals':6}},0)
        self.assertEqual(result['weeks']['1']['lineup_points'],0)
        self.assertEqual(result['weeks']['1']['bench_points'],30)
        self.assertEqual(plan_days(decisions,{'C':1,'BN':1}),plans)

    def test_missing_not_zero_and_late_information_rejected(self):
        decisions=packet();plans=plan_days(decisions,{'C':1,'BN':1})
        result=settle(plans,{'results':[]},{},0)
        self.assertIsNone(result['weeks']['1']['lineup_points'])
        decisions['days'][0]['players'][0]['available_at']='2025-10-02T00:00:00+00:00'
        # Lock equals midnight UTC; equality is allowed, later is rejected.
        decisions['days'][0]['players'][0]['available_at']='2025-10-02T00:01:00+00:00'
        with self.assertRaisesRegex(ValueError,'pre-lock'):plan_days(decisions,{'C':1,'BN':1})

    def test_goalie_nonappearance_and_minimum(self):
        decisions=packet();row=decisions['days'][0]['players'][0]
        row.update(kind='goalie',positions=['G'])
        decisions['days'][0]['players']=[row]
        plans=plan_days(decisions,{'G':1})
        result=settle(plans,{'results':[{'date':'2025-10-01','id':'a','appeared':False,'stats':{},'source':'verified'}]}, {},3)
        self.assertEqual(result['weeks']['1']['goalie_appearances'],0)
        self.assertFalse(result['weeks']['1']['goalie_minimum_met'])
        self.assertEqual(result['weeks']['1']['rule_qualified_points'],0)

    def test_history_cohort_preserves_workhorse_usage(self):
        history=[(str(i),'G','G','goalie',[(2023,60+i,600),(2024,60+i,600)]) for i in range(5)]
        target=('target','Target','G','goalie',[(2024,63,630)])
        expected=cohort_workload(history+[target],'target','goalie',63)
        self.assertGreater(expected,59)
        self.assertEqual(cohort_workload([target],'target','goalie',63),63)
        p=forecast(history+[target],Model(0,.5,'points','cohort'))[-1]
        self.assertGreater(p.games,60)

    def test_nonconsecutive_history_not_a_transition(self):
        history=[(str(i),'G','G','goalie',[(2022,60,600),(2024,10,100)]) for i in range(5)]
        self.assertEqual(cohort_workload(history,'target','goalie',63),63)
