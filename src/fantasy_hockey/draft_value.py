"""Scenario-specific expected active-roster production, independent of external APIs."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from math import isfinite

from .draft import roster_assignment
from .goalie_weeks import weekly_coverage


@dataclass(frozen=True)
class Exposure:
    games: float
    rate: float


@dataclass(frozen=True)
class DraftPlayer:
    id: str
    name: str
    team: str
    kind: str
    positions: tuple[str, ...]
    baseline: Exposure | None
    downside: Exposure | None
    market_rank: float | None = None

    def roster_row(self):
        return {'id':self.id,'positions':self.positions}


def scenario_points(player: DraftPlayer, case: str = 'baseline') -> float:
    exposure=getattr(player,case)
    return exposure.games*exposure.rate if exposure else float('-inf')


class RosterValue:
    """Exact daily slot matching; expected exposure and goalie-week probabilities are proxies."""
    def __init__(self, players: list[DraftPlayer], calendar: dict, slots: dict, *, draft_opportunity=False):
        self.players={p.id:p for p in players};self.calendar=calendar;self.slots=slots
        self.draft_opportunity=draft_opportunity
        if len(self.players)!=len(players):raise ValueError('Duplicate decision player ID')
        self.days=defaultdict(set);self.team_games=Counter()
        for g in calendar['games'].values():
            for team in g['teams']:
                if team in self.days[g['date']]:raise ValueError('Duplicate team/date')
                self.days[g['date']].add(team);self.team_games[team]+=1
        for p in players:
            for exp in (p.baseline,p.downside):
                if exp and (not isfinite(exp.rate) or not isfinite(exp.games) or not 0<=exp.games<=self.team_games[p.team]):
                    raise ValueError(f'Invalid exposure or unknown calendar team: {p.id}')
        self.skater_slots={k:v for k,v in slots.items() if k not in {'G','BN','IR','IR+'}}

    @lru_cache(maxsize=12000)
    def skaters(self, ids: tuple, case: str) -> float:
        return self.active_points(ids,case,self.skater_slots)

    def active_points(self, ids, case, slots):
        rates={pid:self.daily_rate(self.players[pid],case) for pid in ids}
        ordered=sorted((self.players[pid] for pid in ids if rates[pid]>0),key=lambda p:(-rates[p.id],p.id))
        signatures=Counter(tuple(p.id for p in ordered if p.team in teams) for teams in self.days.values())
        result=0
        for signature,count in signatures.items():
            active=[];points=0;counts=Counter()
            if all(len(self.players[pid].positions)==1 for pid in signature):
                for pid in signature:
                    p=self.players[pid];pos=p.positions[0]
                    if counts[pos]<slots.get(pos,0):
                        counts[pos]+=1;points+=rates[pid]
            else:
                # Maximum-weight independent set of the slot-matching matroid.
                for pid in signature:
                    p=self.players[pid];row=p.roster_row()
                    if len(roster_assignment(active+[row],slots))==len(active)+1:
                        active.append(row);points+=rates[pid]
            result+=count*points
        return result

    def daily_rate(self,p,case):
        exp=getattr(p,case)
        if exp is None:raise ValueError(f'Missing {case} projection for owned/candidate player: {p.id}')
        return exp.rate*exp.games/self.team_games[p.team]

    @lru_cache(maxsize=12000)
    def goalies(self,ids: tuple,case: str) -> tuple:
        if self.draft_opportunity:
            # GP forecasts include appearances, not verified starts. Do not feed
            # them into the mutually exclusive starter/weekly qualification model.
            return self.active_points(ids,case,{'G':self.slots.get('G',0)}),None
        rows=[]
        for pid in ids:
            p=self.players[pid];exp=getattr(p,case)
            if exp is None:raise ValueError(f'Missing {case} goalie exposure: {pid}')
            rows.append({'id':pid,'team':p.team,'starts':exp.games,'rate':exp.rate})
        weeks=weekly_coverage(self.calendar,rows,slots=self.slots.get('G',0)) if rows else []
        return (sum(w['qualified_points'] for w in weeks),sum(w['failure_probability_proxy'] for w in weeks))

    def evaluate(self,ids,case='baseline') -> dict:
        if case not in {'baseline','downside'}:raise ValueError('Unknown scenario')
        ids=tuple(sorted(ids))
        if len(set(ids))!=len(ids):raise ValueError('Duplicate roster ID')
        skaters=tuple(pid for pid in ids if self.players[pid].kind=='skater')
        goalies=tuple(pid for pid in ids if self.players[pid].kind=='goalie')
        gp,failed=self.goalies(goalies,case)
        sp=self.skaters(skaters,case)
        return {'points':sp+gp,'skater_points':sp,'goalie_points':gp,'failed_weeks_proxy':failed if goalies else None}
