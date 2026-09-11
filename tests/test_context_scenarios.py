from copy import deepcopy
from datetime import date
from decimal import Decimal
import unittest
from fantasy_hockey.context_scenarios import Phase,project_phases,allocate_starts,validate_evidence,evaluate


class ContextTests(unittest.TestCase):
    def test_staged_recovery_and_no_double_bonus(self):
        rates={'goals':1,'assists':1,'power_play_points':1,'shots_on_goal':3,'hits':2,'plus_minus':0}
        weights={'goals':6,'assists':4,'power_play_points':2,'shots_on_goal':.9,'hits':1,'plus_minus':2}
        result=project_phases('skater',rates,weights,[Phase(Decimal(10),{'goals':Decimal('.5')}),Phase(Decimal(20),{})])
        self.assertEqual(result['stats']['goals'],25)
        self.assertEqual(result['stats']['power_play_points'],30)
        self.assertEqual(result['points'],Decimal('471'))

    def test_invalid_exposure_factors_and_ppp(self):
        rates={'goals':1,'assists':1,'power_play_points':1}
        for phase in [Phase(-1,{}),Phase(85,{}),Phase(10,{'goals':-1}),Phase(10,{'unknown':1}),Phase(10,{'power_play_points':3})]:
            with self.subTest(phase=phase),self.assertRaises(ValueError):project_phases('skater',rates,{'goals':6},[phase])

    def test_joint_starts_require_reserve_and_exact_budget(self):
        self.assertEqual(sum(allocate_starts({'a':46,'b':30,'other':8},84).values()),84)
        for allocation in [{'a':56,'b':40},{'a':46,'b':30},{'a':85,'other':-1}]:
            with self.assertRaises(ValueError):allocate_starts(allocation,84)

    def test_future_evidence_and_stale_review(self):
        case={'assumptions':'Analyst assumption','confirmation_needed':'Verify','evidence':[{'date':'2026-09-09','source':'fixture','fact':'fixture'}],'review_by':'2026-09-10'}
        self.assertEqual(validate_evidence(case,date(2026,9,10)),[])
        with self.assertRaises(ValueError):validate_evidence(case,date(2026,9,8))
        self.assertTrue(validate_evidence(case,date(2026,9,11)))

    def test_goalie_delta_separates_workload_and_rate_and_preserves_board(self):
        board={'season':'2026-27','as_of':'2026-09-10','assumptions':{'season_games':84},
               'scoring':{'goalie':{'wins':5}},'players':[{'id':'a','kind':'goalie','team':'MIN','name':'A','projected_points':100,'points_per_game':2}]}
        case={'name':'case','team':'MIN','starts':{'a':40,'other':44},'relief_appearances':{'a':2},
              'assumptions':'Analyst choice','confirmation_needed':'Verify','evidence':[{'date':'2026-09-09','source':'fixture','fact':'fixture'}],'review_by':'2026-09-12'}
        payload={'season':'2026-27','prior_season':'20252026','skaters':[],'goalie_teams':[case],
                 'goalie_rates':{'a':{'season':'20252026','as_of':'2026-09-10','source':'fixture','per_start':{'wins':.6},'per_relief':{'wins':0}}}}
        before=deepcopy(board);r=evaluate(board,payload,date(2026,9,10))['results'][0]
        self.assertEqual(r['points'],120);self.assertEqual(r['workload_only_delta'],-16)
        self.assertEqual(r['conditional_rate_delta'],36)
        self.assertEqual(r['delta_from_baseline'],r['workload_only_delta']+r['conditional_rate_delta'])
        self.assertEqual(board,before)
        case['relief_appearances']['a']=50
        with self.assertRaises(ValueError):evaluate(board,payload,date(2026,9,10))

    def test_start_adapter_keeps_relief_separate(self):
        import csv
        import tempfile
        from pathlib import Path
        from archive.tg.personal.experiments.build_context_pilot import conditional_rates
        rows=[{'game_id':'2025020001','id':'1','date':'2025-10-07','appeared':True,
               'stats':{'wins':1,'goals_against':2,'saves':30,'shutouts':0}},
              {'game_id':'2025020002','id':'1','date':'2025-10-08','appeared':True,
               'stats':{'wins':0,'goals_against':1,'saves':5,'shutouts':0}}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'goalies.csv'
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=['player_id','game_id','starter']);writer.writeheader()
                writer.writerows([{'player_id':'1','game_id':r['game_id'],'starter':'true' if i==0 else 'false'} for i,r in enumerate(rows)])
            history={'season':'20252026','records':rows}
            r=conditional_rates(history,path,{'1'},date(2026,9,10))['nhl:1']
            self.assertEqual(r['per_start']['saves'],30)
            self.assertEqual(r['per_relief']['saves'],5)
            self.assertEqual(r['start_sample'],1)
            with self.assertRaises(ValueError):conditional_rates(history,path,{'1'},date(2025,10,7))
