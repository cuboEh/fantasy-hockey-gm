"""GM workspace commands and a loopback-only snapshot inspection dashboard."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
import sqlite3
import tomllib
import webbrowser

from . import gm_store
from .gm_state import canonical, timestamp


def make_server(path, port=8766):
    gm_store.view(path)  # Refuse draft databases before opening any listener.
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def allowed(self):
            return self.headers.get('Host') in {
                f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def respond(self, payload, status=200, content_type='application/json'):
            body = payload if isinstance(payload, bytes) else canonical(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-GM-Token', token)
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'nonce-" + token + "'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed():
                self.respond({'error': 'Local access only'}, 403)
                return
            try:
                if self.path == '/':
                    html = Path(__file__).with_name('gm_dashboard.html').read_text().replace('__TOKEN__', token)
                    self.respond(html.encode(), content_type='text/html; charset=utf-8')
                elif self.path == '/api/state':
                    self.respond(gm_store.view(path))
                else:
                    self.respond({'error': 'Not found'}, 404)
            except (OSError, ValueError, sqlite3.Error) as exc:
                self.respond({'error': str(exc)}, 400)

        def do_POST(self):
            if not self.allowed() or not secrets.compare_digest(self.headers.get('X-GM-Token', ''), token):
                self.respond({'error': 'Refresh this local page before importing'}, 403)
                return
            if self.path not in ('/api/import','/api/compare','/api/review'):
                self.respond({'error': 'Not found'}, 404)
                return
            attempt = None
            try:
                if self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('JSON required')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 5_000_000:
                    raise ValueError('Import must be between 1 byte and 5 MB')
                if self.path != '/api/import':
                    self.connection.settimeout(10)
                    raw=self.rfile.read(length)
                    if len(raw)!=length:raise ValueError('Incomplete decision request')
                    request=gm_store.decode(raw)
                    from .gm_state import fields
                    fields(request, {'state_key','request'}, 'decision request')
                    try:
                        result=gm_store.save_decision(path,'pickup' if self.path=='/api/compare' else 'lineup',
                                                      request['request'],request['state_key'])
                    except (ValueError, sqlite3.Error):
                        raise
                    except Exception:
                        self.respond({'error':'Decision calculation failed; refresh inputs and retry. Roster inspection remains available.'},500)
                        return
                    self.respond(result)
                    return
                revision = int(self.headers.get('X-GM-Revision', '-1'))
                attempt = gm_store.begin_import(path, expected_revision=revision)
                self.connection.settimeout(10)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise OSError('Upload ended before the complete snapshot arrived')
                result = gm_store.complete_import(path, attempt, raw)
            except (OSError, ValueError, sqlite3.Error) as exc:
                if attempt is not None:
                    gm_store.fail_import(path, attempt, str(exc))
                try:
                    self.respond({'error': str(exc)}, 400)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                try:
                    self.respond(result)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Commit succeeded; read-back, not a blind retry, determines state.

        def log_message(self, *args):
            pass

    return HTTPServer(('127.0.0.1', port), Handler)


def register(commands):
    parser = commands.add_parser('gm', help='Inspect a separate post-draft GM workspace')
    actions = parser.add_subparsers(dest='gm_action', required=True)
    command = actions.add_parser('settings', help='Normalize a supplied TOML config into a settings component')
    command.add_argument('--config', type=Path, required=True)
    command.add_argument('--output', type=Path, required=True)
    command.add_argument('--source', required=True)
    command.add_argument('--observed-at', required=True)
    command.add_argument('--expires-at')
    command = actions.add_parser('prepare-league', help='Normalize an existing supplied full-league draft snapshot')
    command.add_argument('--input', type=Path, required=True)
    command.add_argument('--settings', type=Path, required=True)
    command.add_argument('--league-id', required=True, help='Local workspace identity, not an inferred Yahoo ID')
    command.add_argument('--source', required=True)
    command.add_argument('--observed-at', required=True)
    command.add_argument('--output', type=Path, required=True)
    command = actions.add_parser('forecast', help='Build dated rate forecasts from saved history and explicit workload')
    command.add_argument('--input', type=Path, required=True)
    command.add_argument('--history', type=Path, nargs='+', required=True)
    command.add_argument('--issued-at', required=True)
    command.add_argument('--horizon-end', required=True)
    command.add_argument('--source', required=True)
    command.add_argument('--participation', type=Path)
    command.add_argument('--model', choices=['gm-rates-1','gm-rates-recency-1'], default='gm-rates-1')
    command.add_argument('--output', type=Path, required=True)
    command = actions.add_parser('evaluate', help='Compare saved pre-game forecast reviews with supplied outcomes')
    command.add_argument('--db',type=Path,required=True)
    command.add_argument('--outcomes',type=Path,required=True)
    command.add_argument('--output',type=Path,required=True)
    for name in ('init', 'import', 'show', 'dashboard'):
        command = actions.add_parser(name)
        command.add_argument('--db', type=Path, required=True)
        if name == 'init':
            command.add_argument('--league-id', required=True)
            command.add_argument('--team-id', required=True)
        elif name == 'import':
            command.add_argument('--input', type=Path, required=True)
        elif name == 'show':
            command.add_argument('--as-of', help='Inspect at an explicit ISO timestamp with timezone')
        else:
            command.add_argument('--port', type=int, default=8766)
            command.add_argument('--open', action='store_true', dest='open_browser')


def handle(args):
    if args.gm_action == 'evaluate':
        from .gm_evaluation import evaluate_frozen
        import json
        if args.output.exists():raise ValueError('Preserve prior evaluation; choose a new output path')
        with gm_store.connect(args.db) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='decisions'").fetchone():
                raise ValueError('Save dated reviews before evaluating outcomes')
            reviews=[{'at':r['at'],'snapshot':json.loads(r['snapshot'])}
                     for r in db.execute('SELECT at,snapshot FROM decisions ORDER BY id')]
        report=evaluate_frozen(reviews,gm_store.decode(args.outcomes.read_bytes()),gm_store.utc_now())
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:stream.write(canonical(report)+'\n')
        args.output.chmod(0o600)
        print('Saved forecast evaluation: '+str(args.output))
    elif args.gm_action == 'forecast':
        from .gm_forecasts import build_forecasts
        if args.output.exists():
            raise ValueError('Preserve dated forecasts; choose a new output path')
        if timestamp(args.issued_at,'issue') > gm_store.utc_now():
            raise ValueError('Forecast issue time cannot be in the future')
        payload = build_forecasts([gm_store.decode(p.read_bytes()) for p in args.history],
            gm_store.decode(args.input.read_bytes()), issued_at=args.issued_at, horizon_end=args.horizon_end,
            source=args.source, model=args.model,
            participation=gm_store.decode(args.participation.read_bytes()) if args.participation else None)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:stream.write(canonical(payload)+'\n')
        args.output.chmod(0o600)
        print('Saved dated forecast snapshot: '+str(args.output))
    elif args.gm_action == 'prepare-league':
        from .gm_settings import league_snapshot
        payload = league_snapshot(gm_store.decode(args.input.read_bytes()),
                                  gm_store.decode(args.settings.read_bytes()), league_id=args.league_id,
                                  source=args.source, observed_at=args.observed_at, now=gm_store.utc_now())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            stream.write(canonical(payload) + '\n')
        args.output.chmod(0o600)
        print('Saved normalized league snapshot: ' + str(args.output))
    elif args.gm_action == 'settings':
        from .gm_settings import settings_component
        with args.config.open('rb') as stream:
            raw = tomllib.load(stream)
        component = settings_component(raw, source=args.source, observed_at=args.observed_at,
                                       expires_at=args.expires_at)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            stream.write(canonical(component) + '\n')
        args.output.chmod(0o600)
        print('Saved settings component: ' + str(args.output))
    elif args.gm_action == 'init':
        gm_store.initialize(args.db, args.league_id, args.team_id)
        print('Created separate GM workspace: ' + str(args.db))
    elif args.gm_action == 'import':
        print(canonical(gm_store.import_file(args.db, args.input)))
    elif args.gm_action == 'show':
        now = timestamp(args.as_of, 'as-of') if args.as_of else None
        print(canonical(gm_store.view(args.db, now=now)))
    else:
        if not 1 <= args.port <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        server = make_server(args.db, args.port)
        url = f'http://127.0.0.1:{server.server_port}'
        print('GM league-state preview: ' + url, flush=True)
        if args.open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0
