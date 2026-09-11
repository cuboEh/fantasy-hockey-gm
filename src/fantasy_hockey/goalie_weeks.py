"""Conditional weekly goalie coverage on a supplied season schedule."""
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite

from .goalie_coverage import qualified_expectation
from .seasonlab import week_key


def weekly_coverage(calendar: dict, goalies: list[dict], minimum: int = 3, slots: int = 2) -> list[dict]:
    """Goalie rows provide starts, team, rate, id and optional first games missed.

Starts are an analyst scenario, not a calibrated forecast. Same-team goalies
are mutually exclusive. Injury blocks are explicit scenarios, never dated news
converted silently into a predicted return date.
"""
    if minimum < 1 or slots < 1:raise ValueError('Positive minimum and slots required')
    if len({g['id'] for g in goalies}) != len(goalies):raise ValueError('Duplicate goalie')
    days = defaultdict(set)
    team_days = defaultdict(list)
    for game in calendar['games'].values():
        day=game['date']
        for team in game['teams']:
            if team in days[day]:raise ValueError('Duplicate team/date in calendar')
            days[day].add(team);team_days[team].append(day)
    if not days:raise ValueError('Empty calendar')
    chance = {}; by_team=defaultdict(list)
    for g in goalies:
        if g['team'] not in team_days:raise ValueError('Goalie team absent from schedule')
        starts=float(g['starts']); rate=float(g['rate']); missed=g.get('first_games_missed',0)
        if not isinstance(missed,int) or missed < 0:raise ValueError('Invalid absence block')
        available=sorted(team_days[g['team']])[missed:]
        if not isinstance(missed,int) or missed < 0 or not isfinite(starts) or not isfinite(rate) or not 0 <= starts <= len(available):
            raise ValueError('Invalid goalie scenario')
        chance[g['id']]={day: starts/len(available) if available else 0 for day in available}
        by_team[g['team']].append(g)
    for team, group in by_team.items():
        for day in team_days[team]:
            if sum(chance[g['id']].get(day,0) for g in group)>1+1e-9:
                raise ValueError('Same-team start scenarios exceed one start per game')
    weeks={}; start=date.fromisoformat(week_key(min(days)));end=date.fromisoformat(max(days))
    while start<=end:
        weeks[start.isoformat()]={'week':start.isoformat(),'events':[], 'collision_days':0,'capacity_opportunities':0,'selected_opportunities':0,
                                 'team_games':{team:0 for team in by_team},'back_to_backs':{team:0 for team in by_team}}
        start+=timedelta(days=7)
    for day, teams in sorted(days.items()):
        row=weeks[week_key(day)]
        for team in by_team:
            if team in teams:
                row['team_games'][team]+=1
                yesterday=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
                row['back_to_backs'][team]+=int(team in days.get(yesterday,set()))
        possible=[g for g in goalies if chance[g['id']].get(day,0)>0]
        row['collision_days']+=int(len(possible)>slots)
        active=sorted(possible,key=lambda g:(-float(g['rate'])*chance[g['id']][day],g['id']))[:slots]
        grouped=defaultdict(list)
        for g in active:grouped[g['team']].append(g)
        row['capacity_opportunities']+=min(slots,len({g['team'] for g in possible}))
        row['selected_opportunities']+=len(grouped)
        for group in grouped.values():
            p=sum(chance[g['id']][day] for g in group)
            reward=sum(chance[g['id']][day]*float(g['rate']) for g in group)
            row['events'].append((min(1,p),reward/p))
    result=[]
    for row in weeks.values():
        events=row.pop('events'); retained,failed=qualified_expectation(events,minimum)
        result.append({**row,'expected_starts':sum(p for p,_ in events),
                       'qualified_points':retained,'failure_probability_proxy':failed,
                       'minimum_impossible':row['capacity_opportunities']<minimum})
    return result
