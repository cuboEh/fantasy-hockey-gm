"""Private OAuth credentials and GET-only access to the official Yahoo API."""

import base64
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

AUTH_URL = 'https://api.login.yahoo.com/oauth2/request_auth'
TOKEN_URL = 'https://api.login.yahoo.com/oauth2/get_token'
API_URL = 'https://fantasysports.yahooapis.com/fantasy/v2'
TEAMS_PATH = '/users;use_login=1/games;game_codes=nhl/teams'


@dataclass(repr=False)
class Credentials:
    client_id: str
    client_secret: str
    redirect_uri: str

    @classmethod
    def load(cls, path):
        values = {}
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.removeprefix('export ').partition('=')
            if not separator:
                raise ValueError('Expected KEY=value assignments in the Yahoo environment file')
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key in values:
                raise ValueError('Duplicate environment key')
            values[key] = value
        keys = ('YAHOO_CLIENT_ID', 'YAHOO_CLIENT_SECRET', 'YAHOO_REDIRECT_URI')
        if any(not values.get(key) for key in keys):
            raise ValueError('Set YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET and YAHOO_REDIRECT_URI in .env')
        result = cls(*(values[key] for key in keys))
        parsed = urlsplit(result.redirect_uri)
        if (parsed.scheme != 'https' or parsed.hostname not in ('localhost', '127.0.0.1')
                or not parsed.port or parsed.username or parsed.password
                or parsed.path != '/oauth/callback' or parsed.query or parsed.fragment):
            raise ValueError('Use https://localhost:PORT/oauth/callback as the registered redirect URI')
        return result

    def authorization_url(self, state):
        return AUTH_URL + '?' + urlencode({
            'client_id': self.client_id, 'redirect_uri': self.redirect_uri,
            'response_type': 'code', 'state': state,
        })


def private_json(path, payload):
    """Replace a private artifact atomically; never expose a partial token file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.yahoo-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(request):
    """Do not follow redirects or expose response bodies containing secrets."""
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(10_000_001)
    except HTTPError as exc:
        raise ValueError(f'Yahoo request failed (HTTP {exc.code}); check app access or reconnect') from None
    except (URLError, OSError):
        raise ValueError('Yahoo could not be reached; check the connection and retry') from None
    if len(raw) > 10_000_000:
        raise ValueError('Yahoo response exceeded the connection-check size limit')
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('Yahoo returned an invalid JSON response') from None
    if not isinstance(payload, dict) or 'error' in payload:
        raise ValueError('Yahoo returned an unsuccessful response')
    return payload


@dataclass(repr=False)
class Client:
    credentials: Credentials
    token_path: Path
    transport: object = field(default=request_json, repr=False)

    def exchange(self, fields, previous=None):
        basic = base64.b64encode(
            f'{self.credentials.client_id}:{self.credentials.client_secret}'.encode()).decode()
        payload = self.transport(Request(TOKEN_URL, data=urlencode({
            **fields, 'redirect_uri': self.credentials.redirect_uri,
        }).encode(), headers={'Authorization': 'Basic ' + basic,
                              'Content-Type': 'application/x-www-form-urlencoded'}, method='POST'))
        refresh = payload.get('refresh_token', (previous or {}).get('refresh_token'))
        access = payload.get('access_token')
        lifetime = payload.get('expires_in')
        if (not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh
                or not isinstance(lifetime, (int, float)) or isinstance(lifetime, bool)
                or not math.isfinite(lifetime) or lifetime <= 0
                or str(payload.get('token_type', '')).lower() != 'bearer'):
            raise ValueError('Yahoo returned incomplete tokens; previous credentials were preserved')
        token = {'access_token': access, 'refresh_token': refresh,
                 'expires_at': time.time() + lifetime,
                 'client_id': self.credentials.client_id}
        private_json(self.token_path, token)
        return token

    def authorize(self, code):
        return self.exchange({'grant_type': 'authorization_code', 'code': code})

    def access_token(self):
        try:
            token = json.loads(self.token_path.read_text())
            valid = (isinstance(token, dict) and token.get('client_id') == self.credentials.client_id
                     and isinstance(token.get('access_token'), str) and bool(token['access_token'])
                     and isinstance(token.get('refresh_token'), str) and bool(token['refresh_token'])
                     and isinstance(token.get('expires_at'), (int, float))
                     and math.isfinite(token['expires_at']))
        except (OSError, ValueError):
            valid = False
        if not valid:
            raise ValueError('No valid saved Yahoo authorization; run fantasy yahoo login')
        if token['expires_at'] <= time.time() + 60:
            token = self.exchange({'grant_type': 'refresh_token',
                                   'refresh_token': token['refresh_token']}, previous=token)
        return token['access_token']

    def read_teams(self):
        """Fixed GET endpoint: no arbitrary URLs, roster writes or snapshot imports."""
        payload = self.transport(Request(API_URL + TEAMS_PATH + '?format=json',
            headers={'Authorization': 'Bearer ' + self.access_token()}, method='GET'))
        if not isinstance(payload.get('fantasy_content'), dict):
            raise ValueError('Yahoo response lacks fantasy content; previous read was preserved')
        return payload
