"""Prior-calendar goalie coverage proxy, not calibrated start probabilities.

Appearance forecasts proxy starts. Same-team goalies share one opportunity;
relief appearances and serial injury dependence are not modeled.
"""
from collections import defaultdict
from functools import lru_cache

from .seasonlab import opportunity_evaluator, week_key


def qualified_expectation(events, minimum=3):
    """Return expected points retained at a minimum and probability of failure.

Each independent event is (appearance probability, points if appearing).
Reward mass is tracked jointly with count, so high-scoring appearances are
not incorrectly treated as independent of qualification.
"""
    if minimum < 1:
        raise ValueError('Minimum must be positive')
    probability = [1.0] + [0.0] * minimum
    reward = [0.0] * (minimum + 1)
    for chance, points in events:
        if not 0 <= chance <= 1:
            raise ValueError('Appearance probability must be between zero and one')
        nxt = [0.0] * (minimum + 1)
        earned = [0.0] * (minimum + 1)
        for count in range(minimum + 1):
            reached = min(minimum, count + 1)
            nxt[count] += probability[count] * (1 - chance)
            earned[count] += reward[count] * (1 - chance)
            nxt[reached] += probability[count] * chance
            earned[reached] += (reward[count] + probability[count] * points) * chance
        probability, reward = nxt, earned
    return reward[minimum], 1 - probability[minimum]


def coverage_evaluator(pool, players, previous_season, slots, minimum=3):
    """Usable production plus marginal protection of existing goalie points.

Never charge an early pick for an unfinished roster's missing goalie partner.
Credit reductions in expected forfeited points, but do not reward deliberately
creating an undercovered roster. Calendar and team identity are prior-year proxies.
"""
    ordinary = opportunity_evaluator(pool, players, previous_season, slots)
    forecasts = {p.id: p for p in pool}
    dates = defaultdict(set)
    for game in previous_season['games'].values():
        dates[game['date']].update(game['teams'])
    # Normalize same-team forecasts across the entire pool, not just owned players.
    totals = defaultdict(float)
    for p in pool:
        if p.position == 'G':
            totals[players[p.id]['team']] += max(0, min(1, p.games / 82))
    chances = {p.id: max(0, min(1, p.games / 82)) /
               max(1, totals[players[p.id]['team']]) for p in pool if p.position == 'G'}

    @lru_cache(maxsize=20000)
    def risk(ids):
        weeks = defaultdict(list)
        raw = 0.0
        for day, teams in sorted(dates.items()):
            active = sorted((forecasts[pid] for pid in ids if players[pid]['team'] in teams
                             and forecasts[pid].rate > 0),
                            key=lambda p: (-p.rate * p.games / 82, p.id))[:slots.get('G', 0)]
            grouped = defaultdict(list)
            for p in active:
                grouped[players[p.id]['team']].append(p)
            for group in grouped.values():
                chance = min(1.0, sum(chances[p.id] for p in group))
                points = sum(chances[p.id] * p.rate for p in group)
                weeks[week_key(day)].append((chance, points / chance if chance else 0))
                raw += points
        retained = sum(qualified_expectation(events, minimum)[0] for events in weeks.values())
        return raw - retained

    def marginal(candidate, own_ids):
        gain = ordinary(candidate, own_ids)
        if candidate.position != 'G':
            return gain
        held = tuple(sorted(pid for pid in own_ids if forecasts[pid].position == 'G'))
        return gain + max(0.0, risk(held) - risk(tuple(sorted((*held, candidate.id)))))

    return marginal


def draft_coverage(players, own_ids, selected, calendar, slots, season_games):
    """Read-only insurance estimates for a live board, using an explicit proxy calendar."""
    from .backtest import Forecast
    if season_games <= 0:
        raise ValueError('Season games must be positive')
    goalies = [p for p in players if p['kind'] == 'goalie']
    known_teams = {t for g in calendar['games'].values() for t in g['teams']}
    missing = [p['id'] for p in goalies if p.get('projected_games') is None
               or p.get('points_per_game') is None or p.get('team') not in known_teams]
    if set(missing) & set(own_ids):
        return {'available': False, 'reason': 'An owned goalie has missing workload, rate or calendar team',
                'excluded_ids': missing, 'candidates': []}
    valid = [p for p in goalies if p['id'] not in missing]
    pool = [Forecast(p['id'], p['name'], 'G', 'goalie', float(p['points_per_game']),
                     float(p['projected_games']) * 82 / season_games, float(p['projected_points']))
            for p in valid]
    metadata = {p['id']: {'team': p['team']} for p in valid}
    held = [p.id for p in pool if p.id in own_ids]
    utility = coverage_evaluator(pool, metadata, calendar, slots)
    ordinary = opportunity_evaluator(pool, metadata, calendar, slots)
    rows = [{'id': p.id, 'name': p.name,
             'insurance_points': utility(p, held) - ordinary(p, held)}
            for p in pool if p.id not in selected]
    return {'available': True, 'owned_goalies': len(held), 'excluded_ids': missing,
            'candidates': sorted(rows, key=lambda r: (-r['insurance_points'], r['id'])),
            'interpretation': 'Experimental protection credit on the supplied prior calendar, not added season projections or calibrated probabilities. Zero with no owned goalies. Missing candidates excluded; roster fit must still be checked.'}
