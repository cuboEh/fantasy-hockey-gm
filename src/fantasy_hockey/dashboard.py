"""Small loopback-only draft dashboard over the existing SQLite tracker."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
from urllib.request import urlopen
import webbrowser

from . import draft
from .board import dump_json
from .preparation import guidance


def state(path: Path) -> dict:
    # The tracker and guide have independent read connections. Do not label an
    # older board with a newer revision if the CLI changes it during these reads.
    for _ in range(3):
        with draft.connect(path) as db:before=db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
        board=draft.draft_board(path,limit=10000);guide=guidance(path,limit=6)
        with draft.connect(path) as db:
            db.execute('BEGIN')
            picks=[dict(r) for r in db.execute('SELECT picks.*, json_extract(players.payload, "$.name") AS name FROM picks JOIN players ON players.id=picks.player_id ORDER BY pick DESC')]
            revision=db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
        if before==revision:
            return {'board':board,'guide':guide,'picks':picks,'revision':revision,'session':path.name}
    raise ValueError('The draft is changing. Refresh to load a consistent view.')


def make_server(path: Path, port: int = 8765, schedule_path: Path | None = None,
                workloads_path: Path | None = None, rates_path: Path | None = None) -> HTTPServer:
    path = path.resolve()
    state(path)  # Fail before opening the listener if the session is unusable.
    token = secrets.token_urlsafe(32)
    comparison_cache={}

    class Handler(BaseHTTPRequestHandler):
        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def respond(self, body, status=200, content_type='application/json', filename=None):
            if not isinstance(body, bytes):body = dump_json(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'nonce-"+token+"'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed_host():self.respond({'error':'Local access only'},403);return
            try:
                if self.path == '/':
                    html = Path(__file__).with_name('dashboard.html').read_text().replace('__TOKEN__',token)
                    self.respond(html.encode(),content_type='text/html; charset=utf-8')
                elif self.path == '/api/state':self.respond({**state(path),'comparison_available':bool(schedule_path and schedule_path.is_file())})
                elif self.path == '/api/health':self.respond({'app':'fantasy-hockey-dashboard','db':str(path)})
                elif self.path == '/backup':
                    with tempfile.TemporaryDirectory() as directory:
                        backup = Path(directory)/'draft.sqlite'
                        with draft.connect(path) as source:
                            target = sqlite3.connect(backup)
                            try:source.backup(target)
                            finally:target.close()
                        self.respond(backup.read_bytes(),content_type='application/vnd.sqlite3',filename='fantasy-draft-backup.sqlite')
                else:self.respond({'error':'Not found'},404)
            except (OSError, ValueError, sqlite3.Error) as exc:self.respond({'error':str(exc)},400)

        def do_POST(self):
            if not self.allowed_host() or not secrets.compare_digest(self.headers.get('X-Draft-Token',''),token):
                self.respond({'error':'Refresh the dashboard before making changes'},403);return
            try:
                if self.headers.get('Content-Type') != 'application/json':raise ValueError('JSON required')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096:raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data,dict) or type(data.get('revision')) is not int:raise ValueError('Refresh the dashboard first')
                revision = data['revision']
                if self.path in {'/api/compare','/api/coverage'}:
                    from .decision_cli import working_snapshot, compare_working, compare_working_completion
                    import hashlib
                    if not schedule_path:raise ValueError('No schedule configured. Basic draft tracking remains available.')
                    snapshot=working_snapshot(path)
                    if snapshot['revision']!=revision:raise ValueError('The draft changed. Refresh before comparing picks.')
                    raw=schedule_path.read_bytes()
                    coverage=self.path=='/api/coverage'
                    selected_id=data.get('selected_id') if not coverage else None
                    if selected_id is not None and (not isinstance(selected_id,str) or not selected_id):raise ValueError('Select a player identity')
                    if coverage and (not workloads_path or not rates_path):
                        raise ValueError('Goalie coverage needs separately reviewed starts and starter rates. Ordinary comparison and tracking remain available.')
                    extra=[p.read_bytes() for p in (workloads_path,rates_path)] if coverage else []
                    key=(self.path,revision,selected_id,*(hashlib.sha256(r).hexdigest() for r in [raw,*extra]))
                    if key not in comparison_cache:
                        try:
                            inputs=[json.loads(r) for r in [raw,*extra]]
                            if any(not isinstance(value,dict) for value in inputs):raise ValueError('Comparison inputs must be JSON objects. Ordinary tracking remains available.')
                            result=compare_working_completion(snapshot,*inputs) if coverage else compare_working(snapshot,inputs[0],selected_id)
                        except (KeyError,TypeError,IndexError,AttributeError) as exc:
                            raise ValueError('Comparison inputs are incomplete or incompatible. Ordinary tracking remains available.') from exc
                        comparison_cache.clear();comparison_cache[key]=result
                    if working_snapshot(path)['revision']!=revision:raise ValueError('The draft changed while calculating. Refresh before comparing picks.')
                    self.respond(comparison_cache[key]);return
                elif self.path == '/api/pick':
                    if not isinstance(data.get('player'),str) or not data['player']:raise ValueError('Select a player')
                    draft.pick_player(path,data['player'],expected_revision=revision)
                elif self.path == '/api/undo':draft.undo(path,expected_revision=revision)
                elif self.path == '/api/slot':
                    if type(data.get('slot')) is not int:raise ValueError('Choose a valid slot')
                    draft.set_slot(path,data['slot'],expected_revision=revision)
                else:self.respond({'error':'Not found'},404);return
                self.respond({'ok':True})
            except (OSError, ValueError, sqlite3.Error) as exc:self.respond({'error':str(exc)},400)

        def log_message(self, *args):pass

    return HTTPServer(('127.0.0.1',port),Handler)


def register(commands):
    parser = commands.add_parser('dashboard',help='Open the local draft dashboard')
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open',action='store_true',dest='open_browser')
    parser.add_argument('--schedule',type=Path,help='Normalized upcoming schedule for pick-now versus wait comparisons')
    parser.add_argument('--workloads',type=Path,help='Reviewed goalie starts for optional final-pick coverage')
    parser.add_argument('--rates',type=Path,help='Previous-season starter rates for optional final-pick coverage')


def handle(args):
    if not 1 <= args.port <= 65535:raise ValueError('Port must be between 1 and 65535')
    url = f'http://127.0.0.1:{args.port}'
    try:server = make_server(args.db,args.port,args.schedule,args.workloads,args.rates)
    except OSError:
        # Reopening the desktop launcher should reuse this exact session only.
        try:
            with urlopen(url+'/api/health',timeout=2) as response:health = json.load(response)
            if health != {'app':'fantasy-hockey-dashboard','db':str(args.db.resolve())}:raise ValueError('Port is in use by a different session or application')
        except (OSError,ValueError) as exc:raise ValueError('Dashboard port is unavailable; choose another port') from exc
        if args.open_browser:webbrowser.open(url)
        print('Dashboard already running: '+url)
        return 0
    print('Draft dashboard: '+url,flush=True)
    if args.open_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0
