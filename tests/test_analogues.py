from copy import deepcopy
import unittest
from research.analogues import candidates,predict,examples


def row(pid,games=60,rate=5):
    return {'id':pid,'name':pid,'kind':'skater','position':'C','group':'F','games':games,'rate':rate,'points':games*rate,'teams_changed':False}


class AnalogueTests(unittest.TestCase):
    def test_future_season_does_not_change_candidate_features(self):
        annual={2024:{'a':row('a')},2025:{'a':row('a',70)},2026:{'a':row('a',82,100)}}
        before=candidates(annual,2026)
        annual[2026]['a']['rate']=9999
        self.assertEqual(candidates(annual,2026),before)

    def test_future_outcomes_and_same_player_excluded(self):
        c=candidates({2024:{'a':row('a')}},2025)[0]
        train=[{**c,'id':str(i),'target':2024,'actual_games':40,'actual_points':200,'actual_rate':5} for i in range(12)]
        before=predict(c,train)
        contaminated=train+[{**train[0],'id':'a','actual_games':9999}]+[{**train[0],'target':2025,'actual_games':9999}]
        self.assertEqual(predict(c,contaminated),before)
        self.assertLess(before['games'],c['baseline_games'])
        self.assertEqual(len(before['neighbors']),12)

    def test_absent_outcomes_retained_as_zero_and_gap_explicit(self):
        annual={2023:{'a':row('a')},2024:{},2025:{}}
        c=candidates(annual,2025)[0]
        self.assertEqual(c['features'][5],1)
        e=examples(annual,2024,2024)[0]
        self.assertEqual(e['actual_points'],0)
        self.assertIsNone(e['actual_rate'])

    def test_sparse_group_uses_baseline(self):
        c=candidates({2024:{'a':row('a')}},2025)[0]
        self.assertTrue(predict(c,[])['fallback'])
        self.assertEqual(predict(c,[])['points'],c['baseline_points'])
        with self.assertRaises(ValueError):predict(c,[],0)
