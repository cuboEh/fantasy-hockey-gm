"""User-operated Yahoo consent with a temporary loopback HTTPS callback."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import ssl
import subprocess
import threading
from urllib.parse import parse_qs, urlsplit

from .providers.yahoo import Client, Credentials, private_json

PRIVATE = Path('private/yahoo')


def register(commands):
    parser = commands.add_parser('yahoo', help='Connect to Yahoo with read-only API access')
    parser.add_argument('action', choices=('login', 'check'))
    parser.add_argument('--env', type=Path, default=Path('.env'))


def callback_handler(credentials, state, outcome, finished):
    expected = urlsplit(credentials.redirect_uri)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(5)
            super().setup()

        def log_message(self, *args):
            pass  # Callback URLs contain authorization codes.

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            status, message = 400, 'Invalid login callback. Return to the terminal.'
            complete = False
            if self.headers.get('Host') != expected.netloc:
                status, message = 403, 'Local callback host required.'
            elif parsed.path == '/':
                status, message = 200, 'Local Yahoo callback is ready. Return to the terminal to continue.'
            elif parsed.path == expected.path and query.get('state') == [state]:
                with outcome['lock']:
                    if outcome.get('received'):
                        status, message = 409, 'This login callback has already been received.'
                    elif query.get('error') or len(query.get('code', [])) == 1:
                        outcome['received'] = True
                        if query.get('error'):
                            outcome['error'] = 'Yahoo authorization was declined or failed; run login again'
                            message = 'Authorization did not complete. Return to the terminal.'
                        else:
                            outcome['code'] = query['code'][0]
                            status, message = 200, 'Authorization received. You can close this tab and return to the terminal.'
                        complete = True
            body = message.encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            finally:
                if complete:
                    finished.set()

    return Handler


def login(client):
    credentials = client.credentials
    parsed = urlsplit(credentials.redirect_uri)
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    PRIVATE.chmod(0o700)
    cert, key = PRIVATE / 'localhost.crt', PRIVATE / 'localhost.key'
    # Short-lived certificate for this loopback listener only. Yahoo connections
    # continue to use normal system certificate verification.
    try:
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '7',
                        '-subj', '/CN=localhost', '-addext',
                        'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                       check=True, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Could not create the local HTTPS certificate; install OpenSSL and retry') from None
    key.chmod(0o600)
    state, outcome, finished = secrets.token_urlsafe(32), {'lock': threading.Lock()}, threading.Event()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', parsed.port),
                                     callback_handler(credentials, state, outcome, finished))
    except OSError:
        raise ValueError('Yahoo callback port is occupied. Stop the local GM server temporarily, then retry login') from None
    with server:
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            print(f'First open https://{parsed.netloc}/ in your browser.')
            print('The temporary local certificate is self-signed. Allow it only for this localhost page.')
            print('Then open this Yahoo consent link and approve Fantasy Sports read access:')
            print(credentials.authorization_url(state), flush=True)
            if not finished.wait(600):
                raise ValueError('Yahoo login timed out after 10 minutes; run login again')
        finally:
            server.shutdown()
            thread.join()
    if 'error' in outcome:
        raise ValueError(outcome['error'])
    client.authorize(outcome['code'])
    print('Yahoo authorization saved privately.', flush=True)


def handle(args):
    client = Client(Credentials.load(args.env), PRIVATE / 'tokens.json')
    try:
        if args.action == 'login':
            login(client)
        payload = client.read_teams()
        private_json(PRIVATE / 'teams.json', {
            'source': 'Yahoo Fantasy Sports API',
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'payload': payload,
        })
    except KeyboardInterrupt:
        raise ValueError('Yahoo login cancelled; run login again when ready') from None
    print('Yahoo hockey-team read succeeded. Private result: private/yahoo/teams.json')
    print('League selection and GM snapshot integration are still pending.')
    return 0
