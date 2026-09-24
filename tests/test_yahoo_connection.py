import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import socket
import ssl
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fantasy_hockey.providers.yahoo import Client, Credentials, NoRedirect, private_json
from fantasy_hockey.yahoo_cli import callback_handler, login


class YahooConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'tokens.json'
        self.credentials = Credentials('example-client', 'example-secret',
                                       'https://localhost:8766/oauth/callback')

    def test_env_loading_and_loopback_restriction(self):
        path = Path(self.temp.name) / '.env'
        prefix = 'YAHOO_CLIENT_ID="example-client"\nYAHOO_CLIENT_SECRET=example-secret\n'
        path.write_text(prefix + 'YAHOO_REDIRECT_URI=https://localhost:8766/oauth/callback\n')
        self.assertEqual(Credentials.load(path).client_id, 'example-client')
        for uri in ('http://localhost:8766/oauth/callback',
                    'https://example.com:8766/oauth/callback',
                    'https://localhost:8766/oauth/callback?code=oops'):
            path.write_text(prefix + 'YAHOO_REDIRECT_URI=' + uri)
            with self.assertRaises(ValueError):
                Credentials.load(path)
        self.assertNotIn('example-secret', repr(self.credentials))

    def test_authorization_url_has_state_and_no_secret(self):
        url = self.credentials.authorization_url('random-state')
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['state'], ['random-state'])
        self.assertEqual(query['redirect_uri'], [self.credentials.redirect_uri])
        self.assertNotIn('example-secret', url)

    def test_token_rotation_and_fixed_get(self):
        private_json(self.path, {'client_id': 'example-client', 'access_token': 'old-access',
                                'refresh_token': 'old-refresh', 'expires_at': 0})
        requests = []
        def transport(request):
            requests.append(request)
            if request.method == 'POST':
                self.assertEqual(parse_qs(request.data.decode())['refresh_token'], ['old-refresh'])
                return {'access_token': 'new-access', 'refresh_token': 'new-refresh',
                        'expires_in': 3600, 'token_type': 'bearer'}
            self.assertEqual(request.get_header('Authorization'), 'Bearer new-access')
            self.assertEqual(request.full_url,
                'https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_codes=nhl/teams?format=json')
            return {'fantasy_content': {'users': {}}}
        Client(self.credentials, self.path, transport).read_teams()
        self.assertEqual([request.method for request in requests], ['POST', 'GET'])
        self.assertEqual(json.loads(self.path.read_text())['refresh_token'], 'new-refresh')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_diagnostic_consent_requests_only_fantasy_read(self):
        url = self.credentials.authorization_url('random-state', explicit_read_scope=True)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['scope'], ['fspt-r'])
        self.assertEqual(query['prompt'], ['consent'])
        self.assertEqual(query['state'], ['random-state'])
        self.assertEqual(query['redirect_uri'], [self.credentials.redirect_uri])
        self.assertNotIn('example-secret', url)

    def test_incomplete_tokens_preserve_previous_file(self):
        private_json(self.path, {'previous': 'unchanged'})
        before = self.path.read_bytes()
        client = Client(self.credentials, self.path, lambda request: {'access_token': 'partial'})
        with self.assertRaises(ValueError):
            client.authorize('code')
        self.assertEqual(self.path.read_bytes(), before)

    def test_refresh_without_rotation_retains_refresh_token(self):
        client = Client(self.credentials, self.path, lambda request: {
            'access_token': 'new', 'expires_in': 3600, 'token_type': 'bearer'})
        result = client.exchange({'grant_type': 'refresh_token'}, {'refresh_token': 'retained'})
        self.assertEqual(result['refresh_token'], 'retained')

    def test_wrong_client_and_invalid_tokens_do_not_call_network(self):
        def unexpected(request):
            self.fail('Invalid local tokens must not cause a request')
        client = Client(self.credentials, self.path, unexpected)
        for payload in ({}, [], {'client_id': 'other', 'access_token': 'a',
                                'refresh_token': 'b', 'expires_at': time.time() + 3600}):
            private_json(self.path, payload)
            with self.assertRaises(ValueError):
                client.read_teams()

    def test_no_redirects_with_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {},
                                                       'https://example.com'))

    def test_callback_rejects_wrong_state_host_and_replay(self):
        self.check_callback(False)

    def test_callback_reports_denial(self):
        self.check_callback(True)

    def test_real_https_listener_exchanges_callback_without_yahoo_network(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        credentials = Credentials('example-client', 'example-secret',
                                  f'https://localhost:{port}/oauth/callback')
        ready, printed, errors = threading.Event(), [], []
        def capture(*args, **kwargs):
            printed.extend(str(arg) for arg in args)
            if any(str(arg).startswith('https://api.login.yahoo.com/') for arg in args):
                ready.set()
        def transport(request):
            self.assertEqual(parse_qs(request.data.decode())['code'], ['synthetic-code'])
            return {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh',
                    'expires_in': 3600, 'token_type': 'bearer'}
        def run():
            try:
                login(Client(credentials, self.path, transport))
            except Exception as exc:
                errors.append(exc)
                ready.set()
        with patch('fantasy_hockey.yahoo_cli.PRIVATE', Path(self.temp.name)), patch('builtins.print', capture):
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            self.assertTrue(ready.wait(10))
            self.assertEqual(errors, [])
            url = next(value for value in printed if value.startswith('https://api.login.yahoo.com/'))
            state = parse_qs(urlsplit(url).query)['state'][0]
            context = ssl.create_default_context(cafile=str(Path(self.temp.name) / 'localhost.crt'))
            connection = http.client.HTTPSConnection('localhost', port, context=context, timeout=5)
            try:
                connection.request('GET', '/oauth/callback?state=' + state + '&code=synthetic-code')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
            finally:
                connection.close()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
        self.assertEqual(json.loads(self.path.read_text())['access_token'], 'synthetic-access')

    def check_callback(self, denied):
        state, outcome, finished = 'test-state', {'lock': threading.Lock()}, threading.Event()
        server = ThreadingHTTPServer(('127.0.0.1', 0), callback_handler(
            self.credentials, state, outcome, finished))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path, host='localhost:8766'):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request('GET', path, headers={'Host': host})
                response = connection.getresponse()
                result = response.status, response.read()
                self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                return result
            finally:
                connection.close()
        try:
            self.assertEqual(request('/oauth/callback?state=wrong&code=secret')[0], 400)
            self.assertEqual(request('/oauth/callback?state=test-state&code=secret', 'evil.test')[0], 403)
            self.assertFalse(finished.is_set())
            suffix = 'error=access_denied' if denied else 'code=secret-code'
            status, body = request('/oauth/callback?state=test-state&' + suffix)
            self.assertEqual(status, 400 if denied else 200)
            self.assertNotIn(b'secret-code', body)
            self.assertTrue(finished.wait(1))
            self.assertIn('error' if denied else 'code', outcome)
            self.assertEqual(request('/oauth/callback?state=test-state&code=another')[0], 409)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
