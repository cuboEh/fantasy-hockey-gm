from copy import deepcopy
from datetime import date
import unittest

from fantasy_hockey.draft_value import DraftPlayer, Exposure, RosterValue
from fantasy_hockey.draft_planner import compare_turns, shortlist
from fantasy_hockey.goalie_rates import estimate_rates


def player(pid,points=10,position='C',team='A',down=None,rank=None):
    return DraftPlayer(pid,pid,team,'goalie' if position=='G' else 'skater',(position,),
                       Exposure(3,points),Exposure(3,points if down is None else down),rank)


def calendar():
    return {'games':{str(i):{'date':f'2026-10-0{i+5}','teams':['A','B']} for i in range(3)}}


class DraftValueTests(unittest.TestCase):
    def test_bench_congestion_and_multi_position_matching(self):
        players=[player('a',20),player('b',10),player('c',8,'LW')]
        value=RosterValue(players,calendar(),{'C':1,'LW':1,'G':2,'BN':2})
        self.assertEqual(value.evaluate(['a','b','c'])['points'],84)
        flexible=DraftPlayer('f','F','A','skater',('C','LW'),Exposure(3,15),Exposure(3,15))
        value=RosterValue(players+[flexible],calendar(),{'C':1,'LW':1,'G':2,'BN':2})
        self.assertEqual(value.evaluate(['a','f','c'])['points'],105)

    def test_goalie_minimum_is_joint_and_downside_changes_value(self):
        a=DraftPlayer('g','G','A','goalie',('G',),Exposure(3,10),Exposure(0,10))
        value=RosterValue([a],calendar(),{'G':2,'BN':1})
        self.assertEqual(value.evaluate(['g'])['points'],30)
        self.assertEqual(value.evaluate(['g'],'downside')['points'],0)

    def test_positional_shortlist_includes_lower_ranked_goalie(self):
        players=[player(str(i),100-i) for i in range(20)]+[player('g',1,'G')]
        chosen=shortlist(players,[],{p.id:p for p in players},{'C':2,'G':2,'BN':4},width=4)
        self.assertIn('g',{p.id for p in chosen})


class TwoTurnTests(unittest.TestCase):
    def test_waiting_and_shared_opponent_preferences(self):
        players=[player('a',20,rank=1),player('b',19,'LW',rank=2),player('c',18,rank=3),
                 player('d',17,'LW',rank=4),player('e',16,rank=5),player('f',15,'LW',rank=6)]
        slots={'C':1,'LW':1,'G':0,'BN':1}
        value=RosterValue(players,calendar(),slots)
        before=deepcopy(players)
        result=compare_turns(players,[],slots,2,1,value,seeds=(0,),width=2)
        self.assertEqual(result['next_turn'],4)
        for r in result['candidates']:
            trace=r['branches'][0]['intervening_picks']
            self.assertEqual([x['pick'] for x in trace],[2,3])
            self.assertNotIn(r['id'],{x['id'] for x in trace})
            later=r['branches'][0]['best_by_case']['baseline']['next_id']
            self.assertNotIn(later,{x['id'] for x in trace}|{r['id']})
        self.assertEqual(players,before)

    def test_coverage_alternative_and_duplicate_seeds(self):
        players=[player('g1',8,'G',team='A'),player('g2',7,'G',team='B')]
        players += [player(str(i),20-i) for i in range(8)]
        slots={'C':1,'G':2,'BN':1}
        value=RosterValue(players,calendar(),slots)
        picks=[{'pick':1,'team':1,'id':'g1'},
               {'pick':2,'team':2,'id':'0'}, {'pick':3,'team':2,'id':'1'}]
        result=compare_turns(players,picks,slots,2,1,value,seeds=(0,))
        alt=result['coverage_alternative']
        self.assertIsNotNone(alt)
        chosen=next(r for r in result['candidates'] if r['id']==alt['id'])
        self.assertGreaterEqual(chosen['two_pick_coverage']['baseline']['minimum_goalies'],2)
        self.assertGreaterEqual(alt['points_cost_vs_baseline_choice'],0)
        with self.assertRaisesRegex(ValueError,'distinct'):
            compare_turns(players,picks,slots,2,1,value,seeds=(0,0))

    def test_unknown_slot_and_off_clock_rejected(self):
        players=[player('a'),player('b'),player('c')];slots={'C':1,'BN':1}
        value=RosterValue(players,calendar(),slots)
        with self.assertRaises(ValueError):compare_turns(players,[],slots,2,0,value)
        with self.assertRaises(ValueError):compare_turns(players,[],slots,2,2,value)


class StarterRateTests(unittest.TestCase):
    def fixture(self):
        records=[];boxes=[]
        for i,(pid,starter,pts) in enumerate([('1','TRUE',10),('1','false',1),('2','true',6)]):
            game='202502000'+str(i)
            records.append({'id':pid,'kind':'goalie','game_id':game,'date':'2026-01-01','appeared':True,'stats':{'saves':pts}})
            boxes.append({'player_id':pid,'game_id':game,'starter':starter})
        return {'season':'20252026','records':records,'source_conflicts':[]},boxes

    def test_starts_relief_and_no_future_or_unknown_classification(self):
        history,boxes=self.fixture()
        r=estimate_rates(history,boxes,{'saves':1},date(2026,9,10),prior_starts=0)['players']['nhl:1']
        self.assertEqual(r['start']['mean_points'],10)
        self.assertEqual(r['relief']['mean_points'],1)
        self.assertEqual(r['start']['sample'],1)
        history['records'][0]['date']='2027-01-01'
        with self.assertRaises(ValueError):estimate_rates(history,boxes,{'saves':1},date(2026,9,10))
        history,boxes=self.fixture();boxes[0]['starter']='unknown'
        with self.assertRaises(ValueError):estimate_rates(history,boxes,{'saves':1},date(2026,9,10))

    def test_conflict_excluded_and_missing_sample_stays_missing(self):
        history,boxes=self.fixture();history['source_conflicts']=[{'id':'1','game_id':boxes[0]['game_id']}]
        r=estimate_rates(history,boxes,{'saves':1},date(2026,9,10))['players']['nhl:1']
        self.assertIsNone(r['start']['shrunk_points'])
        self.assertEqual(r['excluded_conflicts'],1)
