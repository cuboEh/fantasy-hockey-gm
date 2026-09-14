"""Normalize supplied configuration without fetching or inventing league state."""

from copy import deepcopy

from .gm_state import (EXTENDED_RULE_TYPES, LEAGUE_DETAIL_TYPES, RULES,
                       fields, rows, text, timestamp, validate_settings, validate_snapshot)

ALIASES = {'max_acquisitions_per_week': 'acquisition_limit',
           'min_goalie_appearances_per_week': 'goalie_minimum', 'deadline': 'lineup_lock'}


def normalize_settings(raw):
    """Keep supported fields typed and every unrecognized source field explicit."""
    if not isinstance(raw, dict):
        raise ValueError('Supplied configuration must be an object')
    for section in ('league', 'roster', 'scoring', 'rules'):
        if section in raw and not isinstance(raw[section], dict):
            raise ValueError(f'{section}: expected a table/object')
    league = raw.get('league', {})
    config = {name: deepcopy(raw.get(name, {})) for name in ('roster', 'scoring')}
    config['league'] = {'scoring_type': league.get('scoring_type')}
    result = {'config': config, 'timezone': None, 'matchup': None,
              'rules': dict.fromkeys(sorted(RULES | EXTENDED_RULE_TYPES.keys())),
              'league_details': dict.fromkeys(sorted(LEAGUE_DETAIL_TYPES)), 'uninterpreted': {}}
    for key, value in league.items():
        if key in LEAGUE_DETAIL_TYPES:
            result['league_details'][key] = deepcopy(value)
        elif key == 'timezone':
            result['timezone'] = value
        elif key != 'scoring_type':
            result['uninterpreted']['league.' + key] = deepcopy(value)
    assigned = set()
    for key, value in raw.get('rules', {}).items():
        destination = ALIASES.get(key, key)
        if destination in result['rules']:
            if destination in assigned:
                raise ValueError(f'Duplicate settings aliases for {destination}')
            if destination == 'lineup_lock' and value == 'daily-today':
                value = 'daily_today'
            result['rules'][destination] = deepcopy(value)
            assigned.add(destination)
        else:
            result['uninterpreted']['rules.' + key] = deepcopy(value)
    for key in raw.keys() - {'league', 'roster', 'scoring', 'rules'}:
        result['uninterpreted'][key] = deepcopy(raw[key])
    validate_settings(result)
    return result


def settings_component(raw, *, source, observed_at, expires_at=None):
    text(source, 'source')
    observed = timestamp(observed_at, 'observation')
    if expires_at is not None and timestamp(expires_at, 'expiry') <= observed:
        raise ValueError('Expiry must follow observation')
    return {'source': source, 'observed_at': observed_at, 'expires_at': expires_at,
            'coverage': 'complete', 'reason': None, 'data': normalize_settings(raw)}


def league_snapshot(raw, settings, *, league_id, source, observed_at, now):
    """Normalize supplied completed-draft ownership without inventing live lineups.

    IDs are local workspace identities, not guessed Yahoo league/team keys.
    Undrafted players remain unknown availability, never inferred free agents.
    """
    text(league_id, 'local league identity')
    text(source, 'source')
    timestamp(observed_at, 'observation')
    fields(raw, {'teams', 'slot', 'board', 'team_names', 'picks', 'revision'}, 'supplied league snapshot')
    count, selected = raw['teams'], raw['slot']
    if type(count) is not int or not 2 <= count <= 32 or type(selected) is not int or not 1 <= selected <= count:
        raise ValueError('Supplied league has an invalid team count or selected seat')
    if not isinstance(raw['board'], dict):
        raise ValueError('Supplied board must be an object')
    board_players = rows(raw['board'].get('players'), 'supplied players')
    for player in board_players:
        text(player.get('name'), 'supplied player name')
    players = {p['id']: p for p in board_players}
    fields(raw['team_names'], {str(i) for i in range(1, count + 1)}, 'team names')
    if not isinstance(raw['picks'], list):
        raise ValueError('Supplied picks must be a list')
    owned, pick_numbers = {}, set()
    for pick in raw['picks']:
        fields(pick, {'pick', 'team', 'player_id'}, 'pick')
        seat, number, player = pick['team'], pick['pick'], pick['player_id']
        if type(seat) is not int or not 1 <= seat <= count or type(number) is not int or number < 1:
            raise ValueError('Invalid supplied pick/seat')
        if not isinstance(player, str) or player not in players or player in owned or number in pick_numbers:
            raise ValueError('Unresolved or duplicate supplied pick identity')
        owned[player] = seat
        pick_numbers.add(number)
    if pick_numbers != set(range(1, len(pick_numbers) + 1)):
        raise ValueError('Supplied completed draft has gaps in pick sequence')
    settings = deepcopy(settings)
    fields(settings, {'source', 'observed_at', 'expires_at', 'coverage', 'reason', 'data'}, 'settings component')
    text(settings['source'], 'settings source')
    validate_settings(settings['data'])
    config = settings['data']['config']
    if config is None:
        raise ValueError('Supplied roster capacity is required to verify completed draft coverage')
    capacity = sum(v for k, v in config['roster'].items() if k not in {'IR', 'IR+'})
    if any(sum(s == seat for s in owned.values()) != capacity for seat in range(1, count + 1)):
        raise ValueError('Each completed-draft roster must match the supplied active/bench capacity')
    details = settings['data'].setdefault('league_details', {})
    if details.get('team_count') not in (None, count):
        raise ValueError('Supplied settings and league snapshot disagree on team count')
    details['team_count'] = count
    settings['source'] += '; actual team count reconciled with supplied completed-draft rosters'

    def team_id(seat):
        return f'{league_id}:seat:{seat}'

    def envelope(data):
        return {'source': source, 'observed_at': observed_at, 'expires_at': None,
                'coverage': 'complete', 'reason': None, 'data': data}

    def missing(reason):
        return {'source': 'Not supplied', 'observed_at': None, 'expires_at': None,
                'coverage': 'missing', 'reason': reason, 'data': None}

    roster = [{'id': p['id'], 'name': p['name'], 'nhl_team': p.get('team'),
               'positions': p.get('positions') or None, 'selected_position': None}
              for p in board_players if owned.get(p['id']) == selected]
    result = {'schema_version': 1, 'data_type': 'user_supplied',
              'league': {'id': league_id, 'name': 'Supplied league'},
              'team': {'id': team_id(selected), 'name': raw['team_names'][str(selected)]},
              'inputs': {
                  'settings': settings, 'roster': envelope(roster),
                  'players': envelope([{'id': p['id'], 'name': p['name'], 'nhl_team': p.get('team'),
                      'positions': p.get('positions') or None, 'selected_position': None,
                      'can_drop': None, 'injury_slots': None} for p in board_players]),
                  'availability': envelope([{'id': p['id'], 'state': 'owned' if p['id'] in owned else 'unknown',
                                            'owner_team_id': team_id(owned[p['id']]) if p['id'] in owned else None,
                                            'waiver_clears_at': None} for p in board_players]),
                  'league_rosters': envelope([{'id': team_id(seat), 'name': raw['team_names'][str(seat)],
                                               'player_ids': [p for p, s in owned.items() if s == seat],
                                               'player_names': {p: players[p]['name'] for p, s in owned.items() if s == seat}}
                                              for seat in range(1, count + 1)]),
                  'schedule': missing('No verified current schedule interval supplied'),
                  'player_status': missing('No dated current participation/status observations supplied'),
                  'forecasts': missing('Frozen draft projections have not been validated as in-season forecasts'),
              }}
    return validate_snapshot(result, league_id, team_id(selected), now)


def schedule_components(raw):
    """Reuse a saved reciprocal NHL club-schedule normalization, without fetching.

    Preserve its observation time and unknown freshness. Calendar coverage does
    not establish Yahoo matchup boundaries or current postponement knowledge.
    """
    from collections import Counter
    from datetime import timedelta
    from .gm_state import validate_data
    if raw.get('source_kind')!='undocumented_public_endpoint' or not raw.get('sources'):
        raise ValueError('A timestamped normalized club schedule is required')
    games=[{'id':key,'starts_at':r['start'],'teams':r['teams']} for key,r in raw['games'].items()]
    validate_data('schedule',games)
    counts=Counter(t for g in games for t in g['teams'])
    if dict(counts)!=raw.get('team_games'):
        raise ValueError('Schedule game inventory does not match declared team coverage')
    observed=max(timestamp(s['retrieved_at'],'schedule retrieval') for s in raw['sources'])
    starts=[timestamp(g['starts_at'],'game start') for g in games]
    if not starts:raise ValueError('Schedule inventory is empty')
    def envelope(value):
        return {'source':'Saved reciprocal NHL club schedules; publication changes since retrieval unverified',
                'observed_at':observed.isoformat(),'expires_at':None,'coverage':'complete','reason':None,'data':value}
    return {'schedule':envelope(games),'schedule_coverage':envelope({
        'start':(min(starts)-timedelta(days=1)).isoformat(),
        'end':(max(starts)+timedelta(days=1)).isoformat(),'teams':sorted(counts)})}
