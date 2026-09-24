# Yahoo read-only connection

The approved Yahoo app uses a user-operated OAuth consent flow. Credentials alone
do not authorize access to the manager's private leagues. This command verifies
the connection by reading the authenticated user's hockey teams; it does not yet
select a league or import a normalized GM snapshot.

## Configuration

Keep these assignments in the ignored `.env` file, with owner-only permissions:

```dotenv
YAHOO_CLIENT_ID=your-client-id
YAHOO_CLIENT_SECRET=your-client-secret
YAHOO_REDIRECT_URI=https://localhost:8766/oauth/callback
```

Register the same redirect URI in Yahoo My Apps. Do not commit credentials,
authorization links, tokens, certificates or downloaded league data. `.env` and
`private/` are already ignored. Run the commands from the repository root.

## First sign-in

```bash
uv run fantasy yahoo login
```

The callback uses port 8766, which is also the default GM dashboard port. Stop the
GM dashboard temporarily if it occupies that port. The command does not stop
servers or change draft/GM databases itself.

The command creates a temporary self-signed HTTPS certificate using OpenSSL and
prints a local readiness URL followed by a Yahoo authorization URL. First visit
the local readiness URL and allow its certificate for that localhost page only.
Then open the Yahoo URL yourself, sign in, and approve the app's Fantasy Sports
read permission. No Yahoo browser automation is used. The callback validates a
random per-login state value and does not log the authorization code. The login
wait expires after ten minutes. Ctrl+C cancels it.

After consent, tokens are saved to `private/yahoo/tokens.json` with owner-only
permissions. A successful GET saves `private/yahoo/teams.json`, with its observation
time. The terminal displays success and the private path, not the league payload.
An empty team collection does not establish that a particular league is connected.

## Repeat the read

```bash
uv run fantasy yahoo check
```

Expired access tokens refresh automatically, preserving any replacement refresh
token. Failed requests do not overwrite the last successful teams file. That file
remains a dated observation, not a current GM snapshot. If authorization is revoked,
run login again. HTTP 401/403 can also indicate that the approved Fantasy access is
not attached to this Client ID; successful OAuth alone does not prove API access.

## Delivery boundary and evidence

PRD P1-FR5 remains WIP until a real read and league/team reconciliation succeed and
the supported provider produces complete validated GM input. No connected-release
claim follows from unit tests. `tests/test_yahoo_connection.py` verifies private
token replacement, refresh rotation, callback state/host/replay checks, denial,
fixed GET access and credential isolation using synthetic inputs.

Official references, checked September 24, 2026:

- [Yahoo authorization code flow](https://developer.yahoo.com/oauth2/guide/flows_authcode/)
- [HTTPS localhost examples and FAQ](https://developer.yahoo.com/sign-in-with-yahoo/)
- [Fantasy resources and user/team discovery](https://sports.yahoo.com/developer/docs/)

Yahoo still documents `oob`, but the user's registration form rejected it. This
implementation uses the registered HTTPS loopback callback instead.
