"""Atomic local GM imports, kept separate from pure inspection and draft state."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .gm_state import canonical, inspect_snapshot, text, timestamp, validate_snapshot

APP_ID = 0x4648474D
PENDING = 'Import started but completion is unconfirmed; retry with a complete snapshot'


def utc_now():
    return datetime.now(timezone.utc)


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('JSON contains a non-finite number')

    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid snapshot encoding or nesting') from exc


@contextmanager
def connect(path):
    if not path.is_file():
        raise ValueError('GM workspace does not exist; use gm init first')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True)
    db.row_factory = sqlite3.Row
    try:
        if db.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
            raise ValueError('This is not a GM workspace; draft databases cannot be used here')
        with db:
            yield db
    finally:
        db.close()


def initialize(path, league_id, team_id):
    text(league_id, 'league ID')
    text(team_id, 'team ID')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb'):
        pass
    path.chmod(0o600)
    try:
        db = sqlite3.connect(path)
        try:
            with db:
                db.execute(f'PRAGMA application_id={APP_ID}')
                db.execute('CREATE TABLE workspace (id INTEGER PRIMARY KEY CHECK(id=1), league_id TEXT NOT NULL, team_id TEXT NOT NULL)')
                db.execute('INSERT INTO workspace VALUES (1, ?, ?)', (league_id, team_id))
                db.execute('CREATE TABLE imports (id INTEGER PRIMARY KEY, at TEXT NOT NULL, payload TEXT, sha256 TEXT, error TEXT)')
        finally:
            db.close()
    except Exception:
        path.unlink()
        raise


def begin_import(path, *, now=None, expected_revision=None):
    """Commit an attempt before file or transport reads, including on old workspaces."""
    now = now or utc_now()
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        revision = db.execute('SELECT COALESCE(MAX(id),0) FROM imports').fetchone()[0]
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision != revision):
            raise ValueError('The GM workspace changed; refresh before importing')
        return db.execute('INSERT INTO imports(at,error) VALUES (?,?)',
                          (now.isoformat(), PENDING)).lastrowid


def fail_import(path, attempt, message, *, now=None):
    with connect(path) as db:
        db.execute('UPDATE imports SET at=?,error=? WHERE id=? AND error=?',
                   ((now or utc_now()).isoformat(), message, attempt, PENDING))


def complete_import(path, attempt, raw, *, now=None):
    now = now or utc_now()
    failure = None
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        latest = db.execute('SELECT id,error FROM imports ORDER BY id DESC LIMIT 1').fetchone()
        if latest is None or latest['id'] != attempt or latest['error'] != PENDING:
            raise ValueError('Import attempt was superseded or already completed; refresh the workspace')
        workspace = db.execute('SELECT * FROM workspace').fetchone()
        try:
            payload = validate_snapshot(decode(raw), workspace['league_id'], workspace['team_id'], now)
            previous = db.execute('SELECT payload FROM imports WHERE error IS NULL ORDER BY id DESC LIMIT 1').fetchone()
            if previous:
                old = json.loads(previous['payload'])
                if old['inputs'].keys() - payload['inputs'].keys():
                    raise ValueError('Incomplete refresh would discard a previously supplied input envelope')
                for name, component in payload['inputs'].items():
                    former = old['inputs'].get(name)
                    if former is None:
                        continue
                    if former['coverage'] == 'complete' and component['coverage'] == 'missing':
                        raise ValueError(f'{name}: incomplete refresh would discard a previously supplied input')
                    if former['observed_at'] and component['observed_at']:
                        if timestamp(component['observed_at'], name) < timestamp(former['observed_at'], name):
                            raise ValueError(f'{name}: refresh is older than the retained input')
            db.execute('UPDATE imports SET at=?,payload=?,sha256=?,error=NULL WHERE id=?',
                       (now.isoformat(), canonical(payload), hashlib.sha256(raw).hexdigest(), attempt))
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            failure = str(exc) if isinstance(exc, ValueError) else 'Malformed snapshot value or nesting'
            db.execute('UPDATE imports SET at=?,error=? WHERE id=?', (now.isoformat(), failure, attempt))
    if failure:
        raise ValueError(failure)
    return view(path, now=now)


def import_snapshot(path, raw, *, now=None, expected_revision=None):
    attempt = begin_import(path, now=now, expected_revision=expected_revision)
    return complete_import(path, attempt, raw, now=now)


def import_file(path, input_path, *, now=None):
    attempt = begin_import(path, now=now)
    try:
        raw = input_path.read_bytes()
    except OSError:
        fail_import(path, attempt, 'Cannot read supplied snapshot file; previous valid data retained', now=now)
        raise
    return complete_import(path, attempt, raw, now=now)


def view(path, *, now=None):
    now = now or utc_now()
    with connect(path) as db:
        db.execute('BEGIN')
        workspace = dict(db.execute('SELECT league_id,team_id FROM workspace').fetchone())
        latest = db.execute('SELECT id,at,error FROM imports ORDER BY id DESC LIMIT 1').fetchone()
        valid = db.execute('SELECT * FROM imports WHERE error IS NULL ORDER BY id DESC LIMIT 1').fetchone()
        previous = db.execute('SELECT payload FROM imports WHERE error IS NULL ORDER BY id DESC LIMIT 1 OFFSET 1').fetchone()
    revision = latest['id'] if latest else 0
    error = latest['error'] if latest else None
    result = {'workspace': workspace, 'revision': revision, 'checked_at': now.isoformat(),
              'last_attempt_at': latest['at'] if latest else None, 'last_error': error,
              'last_success_at': valid['at'] if valid else None, 'snapshot': None,
              'yahoo_status': 'Read approval pending; no Yahoo connection'}
    if valid:
        result['snapshot'] = json.loads(valid['payload'])
        result['input_sha256'] = valid['sha256']
        result.update(inspect_snapshot(result['snapshot'], now, revision, error))
        for item in result['inputs'].values():
            item['last_success_at'] = valid['at'] if item['coverage'] == 'complete' else None
            item['last_refresh_error'] = error
    else:
        result.update(snapshot_status='empty', inputs={}, issues=['Import a supplied snapshot to inspect league state'],
                      advice_status='unavailable', advice_reason='No snapshot has been imported.', state_key=None)
    if result['snapshot'] is not None:
        from .gm_advice import lineups
        try:
            result['lineups']=lineups(result['snapshot'],now,revision=revision,last_error=error)
        except Exception:
            result['lineups']={'status':'error','reasons':['Lineup calculation failed. Inspect inputs and retry Refresh view.'], 'days':[]}
        status=result['lineups']['status']
        result['advice_status']='available' if status in ('supported','partial') else 'unavailable'
        result['advice_reason']=('Review the dated lineup below; qualification and uncertainty need review.'
            if result['advice_status']=='available' else '; '.join(result['lineups'].get('reasons',[])) or 'No supported lineup available.')
    else:
        result['lineups']={'status':'restricted','reasons':['No supplied snapshot'],'days':[]}
    result['forecast_changes']=[]
    if result['snapshot'] and previous:
        old_forecasts={r['id']:r for r in json.loads(previous['payload'])['inputs']['forecasts']['data'] or []}
        for row in result['snapshot']['inputs']['forecasts']['data'] or []:
            old=old_forecasts.get(row['id'])
            changed=[key for key in ('model_version','model_role','source','issued_at','horizon_start','horizon_end','rates','games','assumptions','missing_inputs')
                     if old is None or old.get(key)!=row.get(key)]
            if changed:
                result['forecast_changes'].append({'id':row['id'],'reason':'First supplied forecast' if old is None else 'Changed forecast inputs: '+', '.join(changed),
                    'fields':changed,'before':old,'after':row})
    result['saved_decisions']=saved_decisions(path,result['state_key'])
    return result


def save_decision(path, kind, request, expected_key, *, now=None):
    """Freeze a reviewed decision with its exact dated input; stale requests fail."""
    from .gm_advice import compare_pickup
    explicit_now=now is not None
    now=now or utc_now()
    state=view(path,now=now)
    if state['state_key']!=expected_key or state['snapshot'] is None:
        raise ValueError('Inputs or time changed; refresh and review the new result')
    if kind=='lineup':
        result=state['lineups']
    elif kind=='pickup':
        if not isinstance(request,dict) or set(request)!={'candidate_id','drop_id'}:
            raise ValueError('Pickup request requires candidate_id and drop_id')
        text(request['candidate_id'],'candidate ID')
        if request['drop_id'] is not None:text(request['drop_id'],'drop ID')
        result=compare_pickup(state['snapshot'],now,request['candidate_id'],request['drop_id'],
                              revision=state['revision'],last_error=state['last_error'])
    else:
        raise ValueError('Unsupported decision kind')
    # Check the real clock again for interactive calls, including locks crossed during calculation.
    check_now=now if explicit_now else utc_now()
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        latest=db.execute('SELECT COALESCE(MAX(id),0) FROM imports').fetchone()[0]
        from .gm_state import inspect_snapshot
        new_key=inspect_snapshot(state['snapshot'],check_now,latest,state['last_error'])['state_key']
        if new_key!=expected_key:
            raise ValueError('Inputs or time changed while calculating; refresh before reviewing')
        db.execute('CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, at TEXT NOT NULL, state_key TEXT NOT NULL, kind TEXT NOT NULL, request TEXT NOT NULL, result TEXT NOT NULL, snapshot TEXT NOT NULL)')
        identity=db.execute('INSERT INTO decisions(at,state_key,kind,request,result,snapshot) VALUES (?,?,?,?,?,?)',
            (now.isoformat(),expected_key,kind,canonical(request),canonical(result),canonical(state['snapshot']))).lastrowid
    return {'id':identity,'at':now.isoformat(),'state_key':expected_key,'kind':kind,'result':result}


def saved_decisions(path, state_key):
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions'").fetchone():return []
        rows=db.execute('SELECT id,at,state_key,kind,request,result FROM decisions ORDER BY id DESC LIMIT 10').fetchall()
    return [{**dict(r),'request':json.loads(r['request']),'result':json.loads(r['result']),
             'historical':r['state_key']!=state_key} for r in rows]


def refresh_from_reader(path, reader, *, now=None, expected_revision=None):
    """Atomic boundary for a separately authorized supported read adapter.

    The reader must return a complete normalized snapshot as bytes. No provider
    requests are made here, and authentication failures never retain current advice.
    """
    attempt=begin_import(path,now=now,expected_revision=expected_revision)
    try:
        raw=reader()
    except PermissionError:
        fail_import(path,attempt,'Read authorization expired or was denied; reconnect through the supported provider flow',now=now)
        raise ValueError('Read authorization expired or was denied') from None
    except (OSError,ValueError):
        fail_import(path,attempt,'Provider refresh did not complete; retained snapshot is historical',now=now)
        raise ValueError('Provider refresh did not complete') from None
    return complete_import(path,attempt,raw,now=now)
