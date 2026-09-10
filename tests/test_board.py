from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fantasy_hockey.board import build_board, export_csv
from fantasy_hockey.config import load_config

ROOT=Path(__file__).resolve().parents[1]


def dataset():
    return {'meta':{'season':'2026-27','seasonGames':84,'generated':'2026-09-01'},
            'players':[{'id':1,'name':'Example Forward','pos':'L','team':'AAA','roster':True,'flags':[],
                'seasons':[{'s':'20252026','gp':82,'cats':{'G':20,'A':30,'PM':-5,'PPP':10,'SOG':200,'HIT':100}},
                           {'s':'20242025','gp':41,'cats':{'G':10,'A':15,'PM':0,'PPP':5,'SOG':100,'HIT':50}}]}],
            'goalies':[{'id':2,'name':'Example Goalie','pos':'G','team':'BBB','flags':[],
                'seasons':[{'s':'20252026','gp':41,'W':20,'GA':100,'SV':1000,'SO':2}]}],
            'consensusOnly':[{'id':3,'name':'Example Rookie','pos':'C','team':'CCC','flags':['noNhlSample']}]}


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/'source.json'
        self.data=dataset()
        self.config=load_config(ROOT/'config.example.toml')

    def build(self, **kwargs):
        self.path.write_text(json.dumps(self.data))
        return build_board(self.path,self.config,date(2026,9,10),**kwargs)

    def test_baseline_uses_custom_weights_and_keeps_unknown_rookie(self):
        board=self.build()
        rows={p['id']:p for p in board['players']}
        player=rows['nhl:1']
        self.assertEqual(player['positions'],['LW'])
        # weighted GP=(82*.6+41*.3)/.9, then 84/82=70; rates remain 20/82 G/game
        self.assertEqual(player['projected_games'],70)
        self.assertAlmostEqual(float(player['stats']['goals']),20/82*70)
        self.assertIsNone(rows['nhl:3']['projected_points'])
        self.assertIn('projection_unavailable',rows['nhl:3']['flags'])
        self.assertIsNone(player['adp'])
        goalie=rows['nhl:2']
        self.assertEqual(goalie['projected_games'],42)
        self.assertAlmostEqual(float(goalie['projected_points']),(20*4-100*2+1000*.2+2*3)/41*42)

    def test_missing_hits_quarantines_instead_of_zero_filling(self):
        del self.data['players'][0]['seasons'][0]['cats']['HIT']
        p=next(p for p in self.build()['players'] if p['id']=='nhl:1')
        self.assertIsNone(p['projected_points'])
        self.assertIn('hits',p['projection_error'])

    def test_duplicate_ids_future_build_and_wrong_season_fail(self):
        self.data['goalies'][0]['id']=1
        with self.assertRaisesRegex(ValueError,'Duplicate identity'):
            self.build()
        self.data=dataset();self.data['meta']['generated']='2026-09-11'
        with self.assertRaisesRegex(ValueError,'after analysis'):
            self.build()
        self.data=dataset();self.data['meta']['season']='2025-26'
        with self.assertRaisesRegex(ValueError,'2026-27'):
            self.build()

    def test_documented_override_and_unknown_identity(self):
        path=self.root/'overrides.json'
        change={'projected_games':60,'positions':['C','LW'],'source':'manual verified example',
                'note':'Fictional test','as_of':'2026-09-10'}
        path.write_text(json.dumps({'nhl:1':change}))
        p=next(p for p in self.build(overrides_path=path)['players'] if p['id']=='nhl:1')
        self.assertEqual(p['projected_games'],60)
        self.assertEqual(p['positions'],['C','LW'])
        self.assertNotIn('eligibility_unverified',p['flags'])
        path.write_text(json.dumps({'nhl:999':change}))
        with self.assertRaisesRegex(ValueError,'Unknown override'):
            self.build(overrides_path=path)

    def test_csv_preserves_unknown_and_provenance(self):
        path=self.root/'board.csv'
        export_csv(self.build(),path)
        text=path.read_text()
        self.assertIn('historical_rate_baseline_v1',text)
        self.assertIn('Example Rookie',text)
        self.assertIn('projection_unavailable',text)

    def test_missing_override_date_has_actionable_error(self):
        path=self.root/'overrides.json'
        path.write_text(json.dumps({'nhl:1':{'source':'manual','note':'test','projected_games':60}}))
        with self.assertRaisesRegex(ValueError,'as_of date'):
            self.build(overrides_path=path)

    def test_optional_analytics_failure_preserves_baseline(self):
        with patch('fantasy_hockey.board.load_moneypuck', return_value={}), \
             patch('fantasy_hockey.board.annotate_moneypuck', side_effect=ValueError('invalid ice time')):
            p=next(p for p in self.build(moneypuck_dir=self.root)['players'] if p['id']=='nhl:1')
        self.assertIsNotNone(p['projected_points'])
        self.assertIn('moneypuck_annotation_unavailable',p['flags'])


if __name__=='__main__':unittest.main()
