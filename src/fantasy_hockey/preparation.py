"""Offline draft preparation. Provider evidence never silently becomes a projection."""
from collections import Counter
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from .board import read_json, normalized_name
from .draft import connect, settings, roster_assignment, snake_team
from .market import load_market
from .scoring import number, score

POSITIONS = {'C', 'LW', 'RW', 'D', 'G'}


def evidence(row: dict, season: str, as_of: date) -> None:
    if row.get('season') != season:
        raise ValueError('Evidence season must match the board')
    if not isinstance(row.get('source'), str) or not row['source'].strip():
        raise ValueError('Evidence needs a source')
    if date.fromisoformat(row.get('as_of', '')) > as_of:
        raise ValueError('Evidence is after analysis date')


def prepare(board: dict, as_of: date, dossier: dict | None = None,
            market_path: Path | None = None) -> dict:
    """Return a new board, preserving the original and existing draft sessions.

    Dossier additions stay unranked unless supplied complete season stat projections.
    Review notes flag uncertainty; they do not imply guessed missed games.
    """
    result = deepcopy(board)
    if date.fromisoformat(board['as_of']) > as_of:
        raise ValueError('Board is after analysis date')
    rows = {p['id']: p for p in result['players']}
    dossier = dossier or {}
    if set(dossier) - {'additions', 'reviews', 'projections'}:
        raise ValueError('Unsupported preparation dossier section')
    for item in dossier.get('additions', []):
        evidence(item, board['season'], as_of)
        pid = item.get('id', '')
        if not pid.startswith('nhl:') or not pid[4:].isdigit() or pid in rows:
            raise ValueError('Additions require a unique verified NHL ID')
        if not item.get('name') or any(normalized_name(p['name']) == normalized_name(item['name']) for p in rows.values()):
            raise ValueError('Missing or duplicate addition name; reconcile identity first')
        positions = item.get('positions', [])
        kind = item.get('kind')
        if kind not in {'skater', 'goalie'} or not positions or set(positions)-POSITIONS:
            raise ValueError('Addition requires kind and primary positions')
        if (kind == 'goalie') != (positions == ['G']) or (kind == 'skater' and 'G' in positions):
            raise ValueError('Addition kind conflicts with positions')
        rows[pid] = {'id':pid, 'external_ids':{'nhl':pid[4:]}, 'name':item['name'],
                     'kind':kind, 'team':item.get('team'), 'positions':positions,
                     'position_source':item['source']+'; primary position, Yahoo unverified',
                     'flags':['eligibility_unverified','projection_unavailable','watchlist_addition'],
                     'projected_points':None,'projected_games':None,'points_per_game':None,
                     'stats':None,'contributions':None,'analytics':None,'adp':None,
                     'addition_evidence':item}
    seen = set()
    for item in dossier.get('reviews', []):
        evidence(item, board['season'], as_of)
        pid = item.get('id')
        if pid not in rows or pid in seen or not item.get('note'):
            raise ValueError('Review needs a unique known player ID and note')
        seen.add(pid)
        if item.get('status') not in {'injury_review','role_review','identity_review','reviewed'}:
            raise ValueError('Unsupported review status')
        player = rows[pid]
        player['review'] = item
        player['flags'] = sorted(set(player['flags']) | {item['status']})
        if 'positions' in item:
            positions = item['positions']
            if item.get('position_provider') != 'Yahoo' or not positions or set(positions)-POSITIONS:
                raise ValueError('Eligibility correction requires explicit Yahoo evidence')
            if (player['kind']=='goalie') != (positions==['G']) or (player['kind']=='skater' and 'G' in positions):
                raise ValueError('Eligibility conflicts with kind')
            player['positions'] = list(dict.fromkeys(positions))
            player['position_source'] = item['source']
            player['flags'].remove('eligibility_unverified') if 'eligibility_unverified' in player['flags'] else None
    seen = set()
    for item in dossier.get('projections', []):
        evidence(item, board['season'], as_of)
        pid = item.get('id')
        if pid not in rows or pid in seen or item.get('basis') != 'season_total':
            raise ValueError('Projection requires unique known ID and season_total basis')
        seen.add(pid)
        player = rows[pid]
        games = number(item.get('games'), 'games')
        if not 0 < games <= number(board['assumptions']['season_games'], 'season_games'):
            raise ValueError('Projection games outside season bounds')
        stats = item.get('stats', {})
        if not isinstance(stats,dict):raise ValueError('Projection stats must be an object')
        scored = score(player['kind'], stats, board['scoring'][player['kind']])
        if player['kind']=='goalie' and any(number(stats.get(k,0),k)>games for k in ('wins','shutouts')):
            raise ValueError('Goalie wins/shutouts exceed appearances')
        if player['kind']=='skater' and number(stats.get('power_play_points',0),'PPP') > number(stats.get('goals',0),'goals')+number(stats.get('assists',0),'assists'):
            raise ValueError('Power-play points exceed goals plus assists')
        player['baseline_projection'] = {k:player.get(k) for k in ('projected_points','projected_games','points_per_game')}
        player.update(projected_points=scored.total, projected_games=games,
                      points_per_game=scored.total/games, stats=item['stats'],
                      contributions={c.stat:c.points for c in scored.contributions}, projection_evidence=item)
        player['flags'] = [f for f in player['flags'] if f not in {'projection_unavailable','workload_carry_forward_review'}]
        player['flags'].append('supplied_projection_unvalidated')
    market = load_market(market_path, board['season'], as_of) if market_path else {}
    if set(market)-set(rows):
        raise ValueError('Unmatched market IDs: '+', '.join(sorted(set(market)-set(rows))))
    if len({(r['metric'],r['source'],r['as_of']) for r in market.values()}) > 1:
        raise ValueError('Use one dated market ranking series per board, not mixed rankings/ADP')
    for pid, item in market.items():
        rows[pid]['market'] = item
        rows[pid]['adp'] = item['value'] if item['metric']=='adp' else None
    result['players'] = sorted(rows.values(), key=point_order)
    result['preparation'] = {'as_of':as_of.isoformat(), 'market_rows_imported':len(market),
                             'market_sha256':hashlib.sha256(market_path.read_bytes()).hexdigest() if market_path else None}
    result['warnings'].append('Preparation notes are review evidence; tiers and scarcity are descriptive, not calibrated probabilities')
    if seen:
        result['model'] += '_with_supplied_projections'
    return result


def point_order(player):
    return (player.get('projected_points') is None,
            -number(player.get('projected_points') or 0, 'points'), player['id'])


def audit(board: dict, teams: int = 14) -> dict:
    players = sorted(board['players'], key=point_order)
    ranked = [p for p in players if p['projected_points'] is not None]
    errors = []
    if len({p['id'] for p in players}) != len(players):errors.append('duplicate player IDs')
    for p in players:
        if (p['kind']=='goalie') != (p['positions']==['G']) or (p['kind']=='skater' and 'G' in p['positions']):
            errors.append(p['id']+': kind/position conflict')
    queue = [{'rank':i if p['projected_points'] is not None else None,
              'id':p['id'],'name':p['name'],'flags':p['flags'], 'review':p.get('review')}
             for i,p in enumerate(players,1) if p['flags']]
    return {'players':len(players),'ranked':len(ranked),'unranked':len(players)-len(ranked),
            'errors':errors,'flag_counts':dict(Counter(f for p in players for f in p['flags'])),
            'market_coverage':sum(bool(p.get('market')) for p in players),
            'active_position_demand':{pos:teams*n for pos,n in board['roster_slots'].items() if pos in POSITIONS},
            'review_queue':queue, 'watchlist':[p for p in players if p['projected_points'] is None]}


def guidance(path: Path, limit: int = 15, tier_width: Decimal = Decimal(50), goalie_calendar: Path | None = None, goalie_workloads: Path | None = None) -> dict:
    """Descriptive draft advice; tiers use anchored 50-point bands per position."""
    if limit < 1 or tier_width <= 0:raise ValueError('Positive limit and tier width required')
    with connect(path) as db:
        info = settings(db)
        players = [json.loads(row[0]) for row in db.execute('SELECT payload FROM players')]
        picks = [dict(row) for row in db.execute('SELECT * FROM picks ORDER BY pick')]
    slots = info['board']['roster_slots']; teams = info['teams']; slot = info['slot']
    if goalie_workloads is not None:
        workloads = json.loads(goalie_workloads.read_text())
        if workloads['season'] != info['board']['season'] or workloads['as_of'] > info['board']['as_of']:
            raise ValueError('Workload review season/date differs from board')
        reviews = {g['id']:g for g in workloads['goalies']}
        for player in players:
            if player['id'] in reviews:
                review = reviews[player['id']]
                if review['team'] != player['team']:raise ValueError('Workload review team differs from board')
                if review.get('evidence') and review['evidence']['date'] > info['board']['as_of']:raise ValueError('Future workload source')
                player['goalie_workload_review'] = review
    selected = {p['player_id'] for p in picks}
    own_ids = {p['player_id'] for p in picks if p['team']==slot}
    own = [p for p in players if p['id'] in own_ids]
    available = sorted((p for p in players if p['id'] not in selected),key=point_order)
    active_slots = {p:n for p,n in slots.items() if p in POSITIONS}
    assigned = roster_assignment(own, active_slots)
    filled = Counter(s.rstrip('0123456789') for s in assigned.values())
    needs = {p:max(0,n-filled[p]) for p,n in active_slots.items()}
    total = sum(n for p,n in slots.items() if p not in {'IR','IR+'})*teams
    upcoming = [i for i in range(len(picks)+1,total+1) if snake_team(i,teams)==slot]
    rows = []
    position_pools = {pos:sorted((p for p in players if pos in p['positions'] and p['projected_points'] is not None),key=point_order) for pos in active_slots}
    for p in available:
        if slot is not None and len(roster_assignment(own+[p],slots)) != len(own)+1:continue
        positions = {}
        for pos in p['positions']:
            pool = position_pools.get(pos,[])
            if not pool or p['projected_points'] is None:continue
            points = number(p['projected_points'],'points')
            demand = teams*active_slots[pos]
            replacement = number(pool[demand]['projected_points'],'points') if len(pool)>demand else None
            remaining = [q for q in pool if q['id'] not in selected]
            anchor = number(pool[0]['projected_points'],'points')
            tier = int((anchor-points)//tier_width)+1
            positions[pos] = {'tier':tier,'active_depth_surplus':points-replacement if replacement is not None else None,
                              'same_tier_remaining':sum(int((anchor-number(q['projected_points'],'points'))//tier_width)+1==tier for q in remaining),
                              'need':needs.get(pos) if slot is not None else None}
        rows.append({**p,'position_context':positions,
                     'review_required': bool(set(p['flags'])-{'reviewed'}),
                     'ten_fewer_appearances_point_change': -min(Decimal(10),number(p['projected_games'],'games'))*number(p['points_per_game'],'rate') if p['projected_points'] is not None else None,
                     'market_before_next_turn': (p['market']['value'] < upcoming[1]) if p.get('market') and len(upcoming)>1 else None})
    coverage = None
    if goalie_calendar is not None:
        from .goalie_coverage import draft_coverage
        calendar = json.loads(goalie_calendar.read_text())
        if not calendar.get('games') or any(g['date'] >= info['board']['as_of'] for g in calendar['games'].values()):
            raise ValueError('Goalie proxy calendar must contain only completed dates before board as-of')
        coverage = draft_coverage(players, own_ids, selected, calendar, slots,
                                  info['board']['assumptions']['season_games'])
        coverage['calendar_sha256'] = hashlib.sha256(goalie_calendar.read_bytes()).hexdigest()
        coverage['slot_known'] = slot is not None
    return {'goalie_coverage':coverage,'teams':teams,'slot':slot,'upcoming_picks':upcoming,'active_needs':needs if slot is not None else None,
            'candidates':rows[:limit],'watchlist':[p for p in available if p['projected_points'] is None],
            'warnings':['Two goalie slots do not guarantee three active appearances per week; assess workload and coverage before filling the bench',
                        'Sorted by baseline season points among fitting players; no experimental policy promotion',
                        'Tiers are 50-point positional bands, not confidence intervals',
                        'Depth surplus uses first player beyond league active-position demand, excludes bench demand and overlaps multi-position pools',
                        'Market-before-next-turn compares a rank/ADP number to a pick, not a probability of availability',
                        'An injury review note does not adjust projected appearances; inspect it before choosing']}
