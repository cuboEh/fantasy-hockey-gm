import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
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
            'roster_slots':{'C':1,'LW':1,'G':1,'BN':1},
            'players':[player(1,['C']),player(2,['LW']),player(3,['G'])]}))
        draft.initialize(self.path,board,2,None)
        self.server=make_server(self.path,0)
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
