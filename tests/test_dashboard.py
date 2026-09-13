import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
from datetime import date, timedelta
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fantasy_hockey import draft
from fantasy_hockey.dashboard import make_server
from test_draft import player


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'session.sqlite'
        board=self.root/'board.json'
        board.write_text(json.dumps({'schema_version':1,'model':'test','warnings':[],
            'season':'2026-27','as_of':'2026-09-11','assumptions':{'season_games':60},
            'roster_slots':{'C':1,'LW':1,'G':1,'BN':1},
            'players':[player(1,['C']),player(2,['LW']),player(3,['G']),player(4,['C','LW']),
                       player(5,['C']),player(6,['G']),player(7,['LW']),player(8,['C'])]}))
        draft.initialize(self.path,board,2,None)
        schedule=self.root/'schedule.json'
        schedule.write_text(json.dumps({'season':'20262027','games':{str(i):{'date':(date(2026,10,1)+timedelta(days=i)).isoformat(),'teams':['AAA','BBB']} for i in range(60)}}))
        self.server=make_server(self.path,0,schedule)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        with urlopen(self.url) as response:html=response.read().decode()
        self.token=re.search("const token='([^']+)'",html).group(1)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def get_state(self):
        with urlopen(self.url+'/api/state') as response:return json.load(response)

    def post(self,action,payload,token=None):
        request=Request(self.url+'/api/'+action,data=json.dumps(payload).encode(),
                        headers={'Content-Type':'application/json','X-Draft-Token':token or self.token})
        with urlopen(request) as response:return json.load(response)

    def test_full_manual_flow_persistence_stale_window_and_backup(self):
        before=self.path.read_bytes();initial=self.get_state()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertIsNone(initial['board']['slot'])
        self.post('slot',{'slot':2,'revision':0})
        with self.assertRaises(HTTPError):self.post('pick',{'player':'nhl:1','revision':0})
        self.assertEqual(self.get_state()['picks'],[])
        self.post('pick',{'player':'nhl:1','revision':1})
        self.post('pick',{'player':'nhl:2','revision':2})
        saved=self.get_state()
        self.assertEqual([p['id'] for p in saved['board']['roster']],['nhl:2'])
        self.assertNotIn('nhl:1',[p['id'] for p in saved['board']['candidates']])
        with urlopen(self.url+'/backup') as response:backup=response.read()
        copy=self.root/'backup.sqlite';copy.write_bytes(backup)
        self.assertEqual(draft.draft_board(copy),draft.draft_board(self.path))
        self.post('undo',{'revision':3})
        self.assertEqual(draft.draft_board(self.path)['pick'],2)
        self.assertEqual(len(self.get_state()['board']['roster']),0)
        with self.assertRaises(HTTPError):self.post('undo',{'revision':3})

    def test_foreign_requests_and_invalid_inputs_cannot_change_picks(self):
        with self.assertRaises(HTTPError) as error:self.post('pick',{'player':'nhl:1','revision':0},'wrong')
        self.assertEqual(error.exception.code,403)
        request=Request(self.url+'/api/state',headers={'Host':'foreign.example'})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)
        for payload in ({'slot':True,'revision':0},{'slot':3,'revision':0},{'slot':1}):
            with self.assertRaises(HTTPError):self.post('slot',payload)
        self.assertEqual(self.get_state()['revision'],0)

    def test_comparison_requires_slot_is_readonly_and_invalidates_on_pick(self):
        with self.assertRaises(HTTPError):self.post('compare',{'revision':0})
        self.post('slot',{'slot':1,'revision':0})
        before=self.path.read_bytes()
        result=self.post('compare',{'revision':1})
        self.assertEqual(result['model'],'working_two_pick_opportunity_v1')
        self.assertEqual(result['revision'],1)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.post('compare',{'revision':1}),result)
        self.post('pick',{'player':'nhl:1','revision':1})
        with self.assertRaises(HTTPError):self.post('compare',{'revision':1})
        with self.assertRaises(HTTPError):self.post('compare',{'revision':2})

    def test_eligibility_and_slot_changes_invalidate_comparison(self):
        self.post('slot',{'slot':1,'revision':0})
        first=self.post('compare',{'revision':1})
        draft.set_positions(self.path,'nhl:1',['C','LW'],'Illustrative eligibility correction')
        with self.assertRaises(HTTPError):self.post('compare',{'revision':1})
        updated=self.get_state()
        result=self.post('compare',{'revision':updated['revision']})
        self.assertNotEqual(first['session_sha256'],result['session_sha256'])
        self.post('slot',{'slot':2,'revision':updated['revision']})
        with self.assertRaises(HTTPError):self.post('compare',{'revision':updated['revision']})
        self.assertEqual(self.get_state()['board']['slot'],2)

    def test_missing_owned_projection_blocks_comparison_but_allows_tracking(self):
        # Fixture mutation precedes draft actions; no live data is involved.
        with draft.connect(self.path) as db:
            row=json.loads(db.execute('SELECT payload FROM players WHERE id=?',('nhl:1',)).fetchone()[0])
            row['projected_points']=None
            db.execute('UPDATE players SET payload=? WHERE id=?',(json.dumps(row),'nhl:1'))
        self.post('slot',{'slot':1,'revision':0})
        for revision,pid in enumerate(('nhl:1','nhl:2','nhl:3'),1):
            self.post('pick',{'player':pid,'revision':revision})
        with self.assertRaises(HTTPError) as error:self.post('compare',{'revision':4})
        self.assertIn('owned player',json.load(error.exception)['error'])
        self.post('pick',{'player':'nhl:4','revision':4})
        self.assertEqual(len(self.get_state()['picks']),4)
