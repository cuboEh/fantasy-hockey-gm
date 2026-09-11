from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import csv
from pathlib import Path
import tempfile
import unittest

from fantasy_hockey.board import build_board, dump_json, export_csv
from fantasy_hockey.config import load_config
from fantasy_hockey import draft
from fantasy_hockey.preparation import prepare, audit, guidance
from test_board import dataset


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source.json'
        self.source.write_text(json.dumps(dataset()))
        config=load_config(Path(__file__).resolve().parents[1]/'config.example.toml')
        self.board=build_board(self.source,config,date(2026,9,10))
        self.evidence={'season':'2026-27','as_of':'2026-09-10','source':'Manual permitted export'}

    def test_consensus_only_goalie_classification(self):
        data=dataset();data['consensusOnly'][0]['pos']='G'
        self.source.write_text(json.dumps(data))
        config=load_config(Path(__file__).resolve().parents[1]/'config.example.toml')
        board=build_board(self.source,config,date(2026,9,10))
        self.assertEqual(board['players'][-1]['kind'],'goalie')
        self.assertEqual(audit(board)['errors'],[])

    def test_review_is_not_a_projection_and_original_is_unchanged(self):
        original=deepcopy(self.board)
        item={**self.evidence,'id':'nhl:1','status':'injury_review','note':'Check dated recovery update'}
        prepared=prepare(self.board,date(2026,9,10),{'reviews':[item]})
        self.assertEqual(self.board,original)
        self.assertEqual(prepared['players'][0]['projected_points'],original['players'][0]['projected_points'])
        self.assertIn('injury_review',prepared['players'][0]['flags'])
        item['as_of']='2026-09-11'
        with self.assertRaises(ValueError):prepare(self.board,date(2026,9,10),{'reviews':[item]})

    def test_additions_keep_unknown_and_duplicate_names_fail(self):
        item={**self.evidence,'id':'nhl:4','name':'New Prospect','kind':'skater','positions':['RW'],'team':'AAA'}
        board=prepare(self.board,date(2026,9,10),{'additions':[item]})
        self.assertIsNone(next(p for p in board['players'] if p['id']=='nhl:4')['projected_points'])
        item['name']='Example Forward'
        with self.assertRaises(ValueError):prepare(self.board,date(2026,9,10),{'additions':[item]})

    def test_projection_requires_all_scored_stats_and_recomputes_points(self):
        item={**self.evidence,'id':'nhl:3','basis':'season_total','games':50,
              'stats':{'goals':10,'assists':20,'plus_minus':0,'power_play_points':8,'shots_on_goal':100,'hits':50}}
        board=prepare(self.board,date(2026,9,10),{'projections':[item]})
        p=next(p for p in board['players'] if p['id']=='nhl:3')
        self.assertIsNotNone(p['projected_points']);self.assertEqual(p['projected_games'],50)
        del item['stats']['hits']
        with self.assertRaisesRegex(ValueError,'Missing'):prepare(self.board,date(2026,9,10),{'projections':[item]})

    def test_market_stays_separate_and_unknown_ids_fail(self):
        market=self.root/'market.csv'
        header='id,season,as_of,source,metric,value\n'
        market.write_text(header+'nhl:1,2026-27,2026-09-10,Yahoo manual,rank,40\n')
        board=prepare(self.board,date(2026,9,10),market_path=market)
        self.assertEqual(board['players'][0]['projected_points'],self.board['players'][0]['projected_points'])
        self.assertEqual(audit(board)['market_coverage'],1)
        market.write_text(header+'nhl:99,2026-27,2026-09-10,Yahoo manual,rank,40\n')
        with self.assertRaisesRegex(ValueError,'Unmatched'):prepare(self.board,date(2026,9,10),market_path=market)
        market.write_text('name,rank\nExample,3\n')
        with self.assertRaisesRegex(ValueError,'CSV requires'):prepare(self.board,date(2026,9,10),market_path=market)

    def test_guidance_unknown_slot_and_readonly_scarcity(self):
        path=self.root/'board.json';path.write_text(dump_json(self.board))
        db=self.root/'draft.sqlite';draft.initialize(db,path,14,None)
        original=db.read_bytes();result=guidance(db)
        self.assertIsNone(result['slot']);self.assertEqual(result['upcoming_picks'],[])
        self.assertIsNone(result['candidates'][0]['position_context']['LW']['active_depth_surplus'])
        self.assertEqual(db.read_bytes(),original)
        draft.set_slot(db,14)
        self.assertEqual(guidance(db)['upcoming_picks'][:4],[14,15,42,43])
        self.assertEqual(guidance(db)['candidates'][0]['ten_fewer_appearances_point_change'], -10*self.board['players'][0]['points_per_game'])

    def test_eligibility_requires_yahoo_and_matching_kind(self):
        item={**self.evidence,'id':'nhl:1','note':'Checked manually','status':'reviewed','positions':['C','LW']}
        with self.assertRaises(ValueError):prepare(self.board,date(2026,9,10),{'reviews':[item]})
        item['position_provider']='Yahoo'
        board=prepare(self.board,date(2026,9,10),{'reviews':[item]})
        self.assertNotIn('eligibility_unverified',board['players'][0]['flags'])
        item['positions']=['G']
        with self.assertRaises(ValueError):prepare(self.board,date(2026,9,10),{'reviews':[item]})

    def test_missing_player_can_be_recorded_during_draft_without_losing_picks(self):
        path=self.root/'board.json';path.write_text(dump_json(self.board))
        db=self.root/'draft.sqlite';draft.initialize(db,path,14,1)
        draft.pick_player(db,'nhl:1')
        item={**self.evidence,'id':'nhl:4','name':'Missing Prospect','kind':'skater','positions':['RW'],'team':'AAA'}
        draft.add_player(db,item,date(2026,9,10))
        self.assertEqual(draft.draft_board(db)['pick'],2)
        self.assertEqual(draft.pick_player(db,'Missing Prospect')['pick'],2)
        with self.assertRaises(ValueError):draft.add_player(db,item,date(2026,9,10))

    def test_market_mixed_series_rejected(self):
        market=self.root/'market.csv'
        market.write_text('id,season,as_of,source,metric,value\nnhl:1,2026-27,2026-09-10,source,rank,40\nnhl:2,2026-27,2026-09-10,source,adp,41\n')
        with self.assertRaisesRegex(ValueError,'one dated'):prepare(self.board,date(2026,9,10),market_path=market)

    def test_new_market_replaces_old_series_and_updates_date(self):
        self.board['players'][1]['market']={'metric':'rank','value':1,'source':'Old proxy'}
        market=self.root/'market.csv'
        market.write_text('id,season,as_of,source,metric,value\nnhl:1,2026-27,2026-09-11,Yahoo,adp,2\n')
        prepared=prepare(self.board,date(2026,9,11),market_path=market)
        self.assertEqual(prepared['as_of'],'2026-09-11')
        self.assertEqual(audit(prepared)['market_coverage'],1)
        self.assertNotIn('market',next(p for p in prepared['players'] if p['id']=='nhl:2'))

    def test_restricted_players_remain_searchable_and_pickable(self):
        self.board['recommendation_policy']='yahoo_and_supplied_projection'
        path=self.root/'board.json';path.write_text(dump_json(self.board))
        db=self.root/'draft.sqlite';draft.initialize(db,path,14,1)
        self.assertEqual(guidance(db)['candidates'],[])
        row=draft.draft_board(db)['candidates'][0]
        self.assertTrue(row['recommendation_restrictions'])
        self.assertEqual(draft.pick_player(db,row['id'])['id'],row['id'])

    def test_team_evidence_and_previous_review_preserved(self):
        self.board['players'][0]['review']={'note':'Existing health concern'}
        item={**self.evidence,'id':'nhl:1','status':'reviewed','note':'Team corrected','team':'BBB'}
        with self.assertRaisesRegex(ValueError,'supporting source'):prepare(self.board,date(2026,9,10),{'reviews':[item]})
        item['team_source']='NHL team release'
        p=prepare(self.board,date(2026,9,10),{'reviews':[item]})['players'][0]
        self.assertEqual(p['team'],'BBB')
        self.assertEqual(p['review_history'][0]['note'],'Existing health concern')

    def test_persisted_decimal_adp_is_compared_numerically(self):
        first,second=self.board['players'][:2]
        first['market']={'metric':'adp','value':Decimal('2.1')}
        second.update(kind=first['kind'],positions=first['positions'])
        second['market']={'metric':'adp','value':Decimal('10.4')}
        path=self.root/'board.json';path.write_text(dump_json(self.board))
        db=self.root/'draft.sqlite';draft.initialize(db,path,14,7)
        result=guidance(db)
        candidate=next(p for p in result['candidates'] if p['id']==first['id'])
        self.assertTrue(candidate['market_before_next_turn'])
        self.assertEqual(candidate['later_market_alternatives'][first['positions'][0]][0]['id'],second['id'])

    def test_csv_fallback_preserves_reviews_and_spreadsheet_safety(self):
        item={**self.evidence,'id':'nhl:1','status':'injury_review','note':'=not a formula'}
        board=prepare(self.board,date(2026,9,10),{'reviews':[item]})
        output=self.root/'fallback.csv';export_csv(board,output)
        with output.open() as stream:row=next(csv.DictReader(stream))
        self.assertEqual(row['review_note'],"'=not a formula")
        self.assertEqual(row['review_source'],self.evidence['source'])

    def test_goalie_workload_notes_do_not_change_draft_or_points(self):
        path=self.root/'board.json';path.write_text(dump_json(self.board))
        db=self.root/'draft.sqlite';draft.initialize(db,path,14,None)
        player=next(p for p in self.board['players'] if p['kind']=='goalie')
        evidence={'id':player['id'],'team':player['team'],'baseline_starts':20,
                  'downside_starts':15,'evidence':{'date':'2026-09-09'}}
        review={'season':self.board['season'],'as_of':'2026-09-10','goalies':[evidence]}
        source=self.root/'workloads.json';source.write_text(json.dumps(review))
        original=db.read_bytes();result=guidance(db,limit=100,goalie_workloads=source)
        row=next(p for p in result['candidates'] if p['id']==player['id'])
        self.assertEqual(row['goalie_workload_review']['baseline_starts'],20)
        self.assertEqual(str(row['projected_points']),str(player['projected_points']))
        self.assertEqual(db.read_bytes(),original)
        review['goalies'][0]['evidence']['date']='2026-09-11'
        source.write_text(json.dumps(review))
        with self.assertRaises(ValueError):guidance(db,goalie_workloads=source)
