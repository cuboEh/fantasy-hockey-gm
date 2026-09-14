"""Pure validation and time-sensitive inspection of supplied GM snapshots.

No provider access, persistence, recommendations or forecast fitting lives here.
"""

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import parse_config

INPUTS = ('settings', 'roster', 'availability', 'schedule', 'player_status', 'forecasts')
OPTIONAL_INPUTS = ('league_rosters', 'players', 'schedule_coverage', 'goalie_results')
POSITIONS = {'C', 'LW', 'RW', 'D', 'G'}
SLOTS = POSITIONS | {'BN', 'IR', 'IR+'}
RULES = {'lineup_lock', 'acquisition_limit', 'acquisitions_used', 'waiver_type',
         'waiver_wait_days', 'goalie_minimum', 'goalie_qualification'}
EXTENDED_RULE_TYPES = {
    'season_acquisitions_unlimited': bool, 'season_trades_unlimited': bool,
    'trade_end_date': 'date', 'allow_draft_pick_trades': bool,
    'waiver_mode': str, 'allow_direct_injury_slot_adds': bool,
    'lock_benched_players': bool, 'cant_cut_list': str, 'trade_review': str,
    'votes_required_to_veto': int, 'trade_reject_days': int,
    'post_draft_players': str, 'start_scoring_week': int,
    'playoff_teams': int, 'playoff_weeks': 'weeks', 'playoff_end_display': str,
    'playoff_tiebreaker': str, 'playoff_reseeding': bool, 'lock_eliminated_teams': bool,
}
LEAGUE_DETAIL_TYPES = {
    'max_teams': int, 'team_count': int, 'season_end': 'date', 'draft_format': str, 'draft_type': str,
    'draft_date': 'date', 'draft_time_display': str, 'draft_pick_seconds': int,
    'cash_league': bool, 'publicly_viewable': bool, 'divisions': bool,
    'invite_permissions': str, 'send_unjoined_email_reminders': bool,
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def timestamp(value, label):
    if not isinstance(value, str):
        raise ValueError(f'{label}: provide an ISO timestamp with timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{label}: invalid timestamp') from exc
    if parsed.tzinfo is None:
        raise ValueError(f'{label}: timezone is required')
    return parsed.astimezone(timezone.utc)


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label}: provide nonempty text')
    return value


def fields(value, required, label, optional=()):
    if (not isinstance(value, dict) or not set(required) <= set(value)
            or set(value) - set(required) - set(optional)):
        raise ValueError(f'{label}: fields must be {", ".join(sorted(required))}')


def validate_optional_fields(data, specifications, label):
    fields(data, (), label, specifications)
    for key, value in data.items():
        if value is None:
            continue
        kind = specifications[key]
        if kind is bool:
            if type(value) is not bool:
                raise ValueError(f'{key}: provide a boolean or null')
        elif kind is int:
            integer(value, key)
        elif kind is str:
            text(value, key)
        elif kind == 'date':
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise ValueError(f'{key}: provide an ISO date') from exc
        elif kind == 'weeks':
            if (not isinstance(value, list) or not value
                    or any(type(w) is not int or w < 1 for w in value)
                    or sorted(set(value)) != value):
                raise ValueError(f'{key}: provide distinct ascending positive week numbers')


def integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label}: provide a nonnegative integer or explicit null')


def rows(value, label):
    if not isinstance(value, list):
        raise ValueError(f'{label}: provide a list')
    seen = set()
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f'{label}: each row must be an object')
        identity = text(row.get('id'), label + '.id')
        if identity in seen:
            raise ValueError(f'{label}: duplicate identity {identity}')
        seen.add(identity)
    return value


def validate_settings(data):
    fields(data, {'config', 'timezone', 'matchup', 'rules'}, 'settings.data',
           {'league_details', 'uninterpreted'})
    if data['config'] is not None:
        parse_config(data['config'])
    if data['timezone'] is not None:
        try:
            ZoneInfo(text(data['timezone'], 'timezone'))
        except ZoneInfoNotFoundError as exc:
            raise ValueError('timezone: unknown IANA timezone') from exc
    if data['matchup'] is not None:
        fields(data['matchup'], {'start', 'end'}, 'matchup')
        try:
            start, end = (date.fromisoformat(data['matchup'][key]) for key in ('start', 'end'))
        except (ValueError, TypeError) as exc:
            raise ValueError('matchup: provide ISO start/end dates') from exc
        if start > end:
            raise ValueError('matchup: start must not follow end')
    fields(data['rules'], RULES, 'rules', EXTENDED_RULE_TYPES)
    for key in RULES:
        value = data['rules'][key]
        if value is None:
            continue
        if key in {'lineup_lock', 'waiver_type', 'goalie_qualification'}:
            text(value, key)  # Preserve unfamiliar rules; inspection restricts advice.
        else:
            integer(value, key)
    limit, used = (data['rules'][key] for key in ('acquisition_limit', 'acquisitions_used'))
    if limit is not None and used is not None and used > limit:
        raise ValueError('acquisitions_used exceeds acquisition_limit')
    validate_optional_fields({k: v for k, v in data['rules'].items() if k not in RULES},
                             EXTENDED_RULE_TYPES, 'extended rules')
    details = data.get('league_details', {})
    validate_optional_fields(details, LEAGUE_DETAIL_TYPES, 'league details')
    if details.get('max_teams') is not None and details.get('team_count') is not None:
        if details['team_count'] > details['max_teams']:
            raise ValueError('team_count exceeds max_teams')
    if 'uninterpreted' in data:
        extra = data['uninterpreted']
        if not isinstance(extra, dict) or any(not isinstance(k, str) or not k.strip() for k in extra):
            raise ValueError('uninterpreted: provide a mapping of source paths to values')
        canonical(extra)  # Retain only finite JSON-compatible values.


def validate_data(name, data):
    if name == 'settings':
        validate_settings(data)
        return
    if name == 'schedule_coverage':
        fields(data, {'start', 'end', 'teams'}, name)
        if timestamp(data['start'], 'coverage start') >= timestamp(data['end'], 'coverage end'):
            raise ValueError('Schedule coverage end must follow start')
        if (not isinstance(data['teams'], list) or not data['teams']
                or any(not isinstance(t,str) or not t.strip() for t in data['teams'])
                or len(set(data['teams'])) != len(data['teams'])):
            raise ValueError('Schedule coverage requires distinct team IDs')
        return
    for row in rows(data, name):
        if name == 'league_rosters':
            fields(row, {'id', 'name', 'player_ids'}, name, {'player_names'})
            text(row['name'], 'team name')
            players = row['player_ids']
            if (not isinstance(players, list)
                    or any(not isinstance(p, str) or not p.strip() for p in players)
                    or len(set(players)) != len(players)):
                raise ValueError('league_rosters: provide unique player IDs for each team')
            if 'player_names' in row:
                fields(row['player_names'], players, 'league player names')
                for value in row['player_names'].values():
                    text(value, 'league player name')
        elif name in ('roster', 'players'):
            fields(row, {'id', 'name', 'nhl_team', 'positions', 'selected_position'}, name, {'can_drop', 'injury_slots'})
            if 'can_drop' in row and row['can_drop'] is not None and type(row['can_drop']) is not bool:
                raise ValueError('can_drop must be boolean or null')
            if 'injury_slots' in row and row['injury_slots'] is not None:
                slots = row['injury_slots']
                if not isinstance(slots,list) or any(v not in ('IR','IR+') for v in slots) or len(set(slots)) != len(slots):
                    raise ValueError('injury_slots must identify supported injury eligibility')
            text(row['name'], 'player name')
            if row['nhl_team'] is not None:
                text(row['nhl_team'], 'NHL team')
            positions = row['positions']
            if positions is not None:
                if (not isinstance(positions, list) or not positions
                        or any(not isinstance(p, str) or p not in POSITIONS for p in positions)
                        or len(set(positions)) != len(positions)):
                    raise ValueError('roster: invalid or duplicate eligibility')
                if 'G' in positions and len(positions) > 1:
                    raise ValueError('roster: goalie cannot also have skater eligibility')
            slot = row['selected_position']
            if slot is not None and (not isinstance(slot, str) or slot not in SLOTS):
                raise ValueError('roster: unknown selected position')
            if slot in POSITIONS and positions is not None and slot not in positions:
                raise ValueError('roster: selected position conflicts with eligibility')
        elif name == 'availability':
            fields(row, {'id', 'state', 'owner_team_id', 'waiver_clears_at'}, name)
            if row['state'] not in ('free_agent', 'waivers', 'owned', 'unknown'):
                raise ValueError('availability: unsupported state')
            if row['state'] == 'owned':
                text(row['owner_team_id'], 'owner team')
            elif row['owner_team_id'] is not None:
                raise ValueError('availability: owner supplied for non-owned player')
            if row['waiver_clears_at'] is not None:
                timestamp(row['waiver_clears_at'], 'waiver clearance')
                if row['state'] != 'waivers':
                    raise ValueError('availability: clearance supplied for non-waiver player')
        elif name == 'schedule':
            fields(row, {'id', 'starts_at', 'teams'}, name)
            timestamp(row['starts_at'], 'game start')
            teams = row['teams']
            if (not isinstance(teams, list) or len(teams) != 2
                    or any(not isinstance(t, str) or not t.strip() for t in teams)
                    or len(set(teams)) != 2):
                raise ValueError('schedule: provide two distinct team identities')
        elif name == 'player_status':
            fields(row, {'id', 'status', 'confirmed'}, name)
            text(row['status'], 'player status')
            if type(row['confirmed']) is not bool:
                raise ValueError('player_status: confirmed must be a boolean')
        elif name == 'goalie_results':
            fields(row, {'id', 'player_id', 'game_id', 'qualified', 'confirmed'}, name)
            text(row['player_id'], 'goalie identity'); text(row['game_id'], 'game identity')
            if type(row['qualified']) is not bool or row['confirmed'] is not True:
                raise ValueError('Goalie results require explicit confirmed qualification')
        else:
            fields(row, {'id', 'model_version', 'issued_at', 'horizon_start', 'horizon_end', 'data_type'}, name,
                   {'kind','source','model_role','training_end','history','rates','games','assumptions','missing_inputs'})
            text(row['model_version'], 'forecast version')
            if row['data_type'] != 'projection':
                raise ValueError('forecasts: historical statistics are not projections')
            issued = timestamp(row['issued_at'], 'forecast issue time')
            start = timestamp(row['horizon_start'], 'forecast horizon start')
            end = timestamp(row['horizon_end'], 'forecast horizon end')
            if not issued <= start < end:
                raise ValueError('forecasts: invalid issue time/horizon')


def validate_snapshot(payload, league_id, team_id, now):
    """Return an independent canonical snapshot or reject the entire import."""
    fields(payload, {'schema_version', 'data_type', 'league', 'team', 'inputs'}, 'snapshot')
    if type(payload['schema_version']) is not int or payload['schema_version'] != 1:
        raise ValueError('Unsupported GM snapshot version')
    if payload['data_type'] not in ('illustrative', 'user_supplied'):
        raise ValueError('Snapshot must be explicitly illustrative or user_supplied')
    for key, expected in (('league', league_id), ('team', team_id)):
        fields(payload[key], {'id', 'name'}, key)
        text(payload[key]['name'], key + ' name')
        if payload[key]['id'] != expected:
            raise ValueError(f'Wrong {key}: snapshot does not match this GM workspace')
    fields(payload['inputs'], INPUTS, 'inputs', OPTIONAL_INPUTS)
    for name, component in payload['inputs'].items():
        fields(component, {'source', 'observed_at', 'expires_at', 'coverage', 'reason', 'data'}, name)
        text(component['source'], name + ' source')
        if component['coverage'] == 'missing':
            text(component['reason'], name + ' missing reason')
            if any(component[k] is not None for k in ('data', 'observed_at', 'expires_at')):
                raise ValueError(f'{name}: missing input must have null data and timestamps')
            continue
        if component['coverage'] != 'complete':
            raise ValueError(f'{name}: partial/failed input cannot replace a valid snapshot')
        if component['reason'] is not None:
            raise ValueError(f'{name}: complete input must have null missing reason')
        observed = timestamp(component['observed_at'], name + ' observation')
        if observed > now:
            raise ValueError(f'{name}: observation is in the future')
        if component['expires_at'] is not None:
            if timestamp(component['expires_at'], name + ' expiry') <= observed:
                raise ValueError(f'{name}: expiry must follow observation')
        validate_data(name, component['data'])
        if name == 'forecasts' and any(timestamp(r['issued_at'], 'forecast issue') > observed for r in component['data']):
            raise ValueError('forecasts: issue time follows source observation')
    inputs = payload['inputs']
    roster = inputs['roster']['data'] or []
    availability = {r['id']: r for r in inputs['availability']['data'] or []}
    roster_ids = {p['id'] for p in roster}
    for player in roster:
        entry = availability.get(player['id'])
        if entry and (entry['state'] != 'owned' or entry['owner_team_id'] != team_id):
            raise ValueError('Roster and availability disagree on player ownership')
    if inputs['roster']['coverage'] == 'complete' and any(
            entry['owner_team_id'] == team_id and entry['id'] not in roster_ids
            for entry in availability.values()):
        raise ValueError('Availability assigns an absent roster player to the selected team')
    league_rosters = (inputs.get('league_rosters') or {}).get('data')
    if league_rosters is not None:
        ownership = {}
        for team in league_rosters:
            for player_id in team['player_ids']:
                if player_id in ownership:
                    raise ValueError('league_rosters: player assigned to more than one team')
                ownership[player_id] = team['id']
                entry = availability.get(player_id)
                if entry is None or entry['state'] != 'owned' or entry['owner_team_id'] != team['id']:
                    raise ValueError('league_rosters and availability disagree')
        for entry in availability.values():
            if entry['state']=='owned' and ownership.get(entry['id'])!=entry['owner_team_id']:
                raise ValueError('Availability ownership is absent from supplied league_rosters')
        selected = next((t for t in league_rosters if t['id'] == team_id), None)
        if selected is None or set(selected['player_ids']) != roster_ids:
            raise ValueError('Selected roster differs from league_rosters')
    catalog = {p['id']: p for p in (inputs.get('players') or {}).get('data') or []}
    for player in roster:
        if player['id'] in catalog:
            for key in ('name','positions','nhl_team'):
                if catalog[player['id']][key] != player[key]:
                    raise ValueError('Player catalog and roster disagree')
    result_games = {g['id']: g for g in inputs['schedule']['data'] or []}
    seen_results = set()
    for result in (inputs.get('goalie_results') or {}).get('data') or []:
        key = (result['player_id'], result['game_id'])
        if key in seen_results:
            raise ValueError('Duplicate goalie qualification result')
        seen_results.add(key)
        game = result_games.get(result['game_id'])
        if game is None or timestamp(game['starts_at'],'game start') >= timestamp(inputs['goalie_results']['observed_at'],'results observation'):
            raise ValueError('Confirmed goalie result requires an already started scheduled game')
    config = (inputs['settings']['data'] or {}).get('config')
    for forecast in inputs['forecasts']['data'] or []:
        if 'rates' in forecast:
            if config is None:
                raise ValueError('Numerical forecasts require scoring settings')
            from .gm_forecasts import validate_numeric_forecast
            validate_numeric_forecast(forecast, config['scoring'])
            games = {g['id']: g for g in inputs['schedule']['data'] or []}
            player = catalog.get(forecast['id']) or next((p for p in roster if p['id']==forecast['id']),None)
            for game in forecast['games']:
                actual = games.get(game['game_id'])
                if actual is None or timestamp(actual['starts_at'],'start') != timestamp(game['starts_at'],'start'):
                    raise ValueError('Forecast game differs from supplied schedule')
                if player and player['nhl_team'] not in actual['teams']:
                    raise ValueError('Forecast game does not include player team')
    if config is not None:
        counts = Counter(p['selected_position'] for p in roster if p['selected_position'] is not None)
        if any(count > config['roster'].get(slot, 0) for slot, count in counts.items()):
            raise ValueError('Roster selected positions exceed configured slot capacity')
    return json.loads(canonical(payload))


def inspect_snapshot(payload, now, revision, last_error=None):
    """Inspect freshness and build an advice identity that changes at time boundaries."""
    result = {'inputs': {}, 'issues': [], 'locked_game_ids': [], 'next_change_at': None}
    boundaries = []
    for name, component in payload['inputs'].items():
        status = 'missing'
        if component['coverage'] == 'complete':
            expiry = component['expires_at']
            status = 'freshness_unknown' if expiry is None else 'current'
            if timestamp(component['observed_at'], 'observation') > now:
                status = 'not_yet_observed'
            elif expiry is not None:
                deadline = timestamp(expiry, 'expiry')
                if now >= deadline:
                    status = 'expired'
                else:
                    boundaries.append(deadline)
        count = len(component['data']) if isinstance(component['data'], list) else None
        result['inputs'][name] = {k: component[k] for k in ('source', 'observed_at', 'expires_at', 'coverage', 'reason')}
        result['inputs'][name].update(status=status, records=count)
        if status != 'current':
            result['issues'].append(f'{name}: {component["reason"] or status.replace("_", " ")}')
    settings = payload['inputs']['settings']['data'] or {}
    for key in ('config', 'timezone', 'matchup'):
        if settings.get(key) is None:
            result['issues'].append(f'settings: {key} is unknown')
    rules = settings.get('rules') or dict.fromkeys(RULES)
    supported = {'lineup_lock': {'daily_today'}, 'goalie_qualification': {'active_appearances'}}
    for key, value in sorted(rules.items()):
        if value is None:
            result['issues'].append(f'rules: {key} is unknown')
        elif key in supported and value not in supported[key]:
            result['issues'].append(f'rules: {key} is not supported ({value})')
    details = settings.get('league_details', {})
    if details.get('team_count') is None:
        result['issues'].append('league: actual team count is unknown; maximum capacity is not participation')
    for key in settings.get('uninterpreted', {}):
        result['issues'].append(f'settings: {key} is retained but not interpreted')
    roster = payload['inputs']['roster']['data'] or []
    inventories = {name: {r['id']: r for r in payload['inputs'][name]['data'] or []}
                   for name in ('availability', 'player_status', 'forecasts')}
    schedule_teams = {team for game in payload['inputs']['schedule']['data'] or [] for team in game['teams']}
    for player in roster:
        for key in ('nhl_team', 'positions', 'selected_position'):
            if player[key] is None:
                result['issues'].append(f'{player["name"]}: {key} is unknown')
        for name, inventory in inventories.items():
            if player['id'] not in inventory:
                result['issues'].append(f'{player["name"]}: no {name.replace("_", " ")} record supplied')
        status = inventories['player_status'].get(player['id'])
        if status and (not status['confirmed'] or status['status'] == 'unknown'):
            result['issues'].append(f'{player["name"]}: participation is unconfirmed')
        if player['nhl_team'] and player['nhl_team'] not in schedule_teams:
            result['issues'].append(f'{player["name"]}: no team games supplied; schedule coverage is unverified')
    for game in payload['inputs']['schedule']['data'] or []:
        start = timestamp(game['starts_at'], 'game start')
        if start <= now:
            result['locked_game_ids'].append(game['id'])
        else:
            boundaries.append(start)
    cleared = []
    for player in payload['inputs']['availability']['data'] or []:
        if player['waiver_clears_at']:
            deadline = timestamp(player['waiver_clears_at'], 'waiver clearance')
            if deadline <= now:
                cleared.append(player['id'])
                result['issues'].append(f'{player["id"]}: waiver time passed; refresh ownership before acting')
            else:
                boundaries.append(deadline)
    zone = ZoneInfo(settings.get('timezone') or 'UTC')
    local_day = now.astimezone(zone).date()
    local_date = local_day.isoformat()
    boundaries.append(datetime.combine(local_day + timedelta(days=1), time(), zone).astimezone(timezone.utc))
    if settings.get('matchup') and not settings['matchup']['start'] <= local_date <= settings['matchup']['end']:
        result['issues'].append('settings: supplied matchup does not contain the current local date')
    if last_error:
        result['issues'].insert(0, 'Last import is incomplete or failed; retained snapshot is historical until a successful import')
    result['next_change_at'] = min(boundaries).isoformat() if boundaries else None
    result['locked_game_ids'].sort()
    result['state_key'] = hashlib.sha256(canonical({
        'snapshot': payload, 'revision': revision, 'input_status': result['inputs'],
        'locked': result['locked_game_ids'], 'cleared': sorted(cleared), 'local_date': local_date,
        'last_error': last_error,
    }).encode()).hexdigest()
    result['advice_status'] = 'unavailable'
    result['advice_reason'] = 'GM recommendations are not implemented in this league-state preview.'
    result['snapshot_status'] = 'historical' if last_error or result['issues'] else 'current_inputs'
    return result
