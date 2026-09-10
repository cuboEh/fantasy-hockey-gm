import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fantasy_hockey import draft

ROOT=Path(__file__).resolve().parents[1]


def player(i,positions,points=100):
    return {'id':f'nhl:{i}','name':f'Player {i}','positions':positions,
            'kind':'goalie' if positions==['G'] else 'skater','team':'AAA','projected_points':points,
            'projected_games':60,'points_per_game':2,'flags':['eligibility_unverified']}


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'draft.sqlite'
        self.board=self.root/'board.json'
        self.board.write_text(json.dumps({'schema_version':1,'model':'test','warnings':[],
            'roster_slots':{'C':1,'LW':1,'G':1,'BN':1,'IR':2},
            'players':[player(1,['C']),player(2,['C','LW']),player(3,['G']),player(4,['LW']),
                       player(5,['C']),player(6,['G']),player(7,['LW']),player(8,['C'])]}))
        draft.initialize(self.path,self.board,2,1)

    def test_snake_order(self):
        self.assertEqual([draft.snake_team(i,3) for i in range(1,13)],[1,2,3,3,2,1,1,2,3,3,2,1])

    def test_picks_survive_reopen_duplicate_rejected_undo_audited(self):
        draft.pick_player(self.path,'nhl:1')
        draft.pick_player(self.path,'Player 2')
        self.assertEqual(draft.draft_board(self.path)['pick'],3)
        with self.assertRaisesRegex(ValueError,'already'):
            draft.pick_player(self.path,'nhl:1')
        undone=draft.undo(self.path)
        self.assertEqual(undone['player_id'],'nhl:2')
        self.assertEqual(draft.draft_board(self.path)['pick'],2)
        with draft.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],3)

    def test_existing_database_not_overwritten(self):
        draft.pick_player(self.path,'nhl:1')
        with self.assertRaises(FileExistsError):
            draft.initialize(self.path,self.board,2,2)
        self.assertEqual(draft.draft_board(self.path)['pick'],2)

    def test_matching_reassigns_flexible_players(self):
        result=draft.roster_assignment([player(1,['C','LW']),player(2,['C'])],{'C':1,'LW':1})
        self.assertEqual(result,{'nhl:1':'LW1','nhl:2':'C1'})
        self.assertEqual(len(draft.roster_assignment([player(1,['G']),player(2,['G'])],{'G':1,'IR':3})),1)

    def test_full_draft_boundaries_and_correct_team(self):
        teams=[draft.pick_player(self.path,f'nhl:{i}')['team'] for i in range(1,9)]
        self.assertEqual(teams,[1,2,2,1,1,2,2,1])
        self.assertIsNone(draft.draft_board(self.path)['pick'])
        with self.assertRaisesRegex(ValueError,'complete'):
            draft.pick_player(self.path,'nhl:1')

    def test_slot_and_positions_updates(self):
        draft.set_slot(self.path,2)
        draft.set_positions(self.path,'nhl:1',['C','LW'],'Yahoo checked manually in test')
        board=draft.draft_board(self.path,search='Player 1')
        self.assertEqual(board['slot'],2)
        self.assertEqual(board['your_next_pick'],2)
        self.assertEqual(board['candidates'][0]['positions'],['C','LW'])
        with self.assertRaises(ValueError):draft.set_slot(self.path,3)
        with self.assertRaises(ValueError):draft.set_positions(self.path,'nhl:1',['G'],'test')

    def test_export_and_ambiguous_search(self):
        with self.assertRaisesRegex(ValueError,'one player'):
            draft.pick_player(self.path,'Player')
        destination=self.root/'export.json';draft.export_draft(self.path,destination)
        self.assertEqual(len(json.loads(destination.read_text())['players']),8)

    def test_cli_read_and_invalid_limit(self):
        cmd=[sys.executable,'-m','fantasy_hockey.cli','draft','board','--db',str(self.path)]
        run=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('PROVISIONAL',run.stdout)
        bad=subprocess.run(cmd+['--limit','0'],capture_output=True,text=True)
        self.assertEqual(bad.returncode,2)


if __name__=='__main__':unittest.main()
