"""Reconstructed historical draft, daily lineup and streaming experiments.

Uses prior-season player universe and positions, inferred team changes only
following observed games, and final schedules. These are research simulations,
not verified historical Yahoo leagues or an untouched holdout.
"""
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import date,timedelta
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from .backtest import Model,forecast,mock_draft
from .config import load_config
from .market import load_market,compare_market


def prepare_history(seasons,target):
    players={}
    for year in sorted(y for y in seasons if target-3<=y<target):
        season=seasons[year];totals=defaultdict(lambda:[0,0])
        for row in sorted(season['records'],key=lambda r:(r['date'],r['game_id'])):
            p=players.setdefault(row['id'],{'id':row['id'],'history':[]})
            p.update(name=row['name'],position=row['position'],kind=row['kind'],team=row['team'])
            if row['appeared']:
                totals[row['id']][0]+=1;totals[row['id']][1]+=row['points']
        for identity,(gp,points) in totals.items():
            # Completed historical schedules are known at the next draft.
            # Last-team schedule is an explicit proxy for traded players.
            opportunities=season['team_games'][players[identity]['team']]
            scale=82/opportunities
            players[identity]['history'].append((year,gp*scale,points*scale))
    players={k:v for k,v in players.items() if v['history'] and v['position'] in {'C','LW','RW','D','G'}}
    history=[(p['id'],p['name'],p['position'],p['kind'],p['history']) for p in players.values()]
    return players,history


def week_key(day):
    d=date.fromisoformat(day);return (d-timedelta(days=d.weekday())).isoformat()


def choose_daily(roster,forecasts,teams,scheduled,slots):
    """Single historical position per player. No outcomes enter selection."""
    groups=defaultdict(list)
    for identity in roster:
        p=forecasts[identity]
        if teams[identity] in scheduled:
            groups[p.position].append((p.rate*p.games/82,identity))
    return {identity for pos,rows in groups.items() for value,identity in sorted(rows,reverse=True)[:slots.get(pos,0)] if value>0}


def weekly_value(roster,forecasts,teams,upcoming,slots):
    return sum(sum(forecasts[p].rate*forecasts[p].games/82 for p in choose_daily(roster,forecasts,teams,s,slots)) for s in upcoming)


def valid_roster(roster,forecasts,slots):
    counts=Counter(forecasts[p].position for p in roster)
    return sum(max(0,n-slots.get(p,0)) for p,n in counts.items())<=slots.get('BN',0)


def replay_season(season,picks,forecasts,players,slots,seat,stream=False,max_acquisitions=4,waiver_days=2):
    """Decision at each day's first game. Outcomes revealed only afterward.

    Other teams keep drafted ownership. Waivers are a configurable cooldown,
    not claims. No same-day post-lock transactions or forecasts from outcomes.
    """
    if max_acquisitions<0 or waiver_days<0:raise ValueError('Invalid transaction assumptions')
    own={p['id'] for p in picks if p['team']==seat};drafted={p['id'] for p in picks}
    free=set(forecasts)-drafted;teams={p:v['team'] for p,v in players.items()}
    # Protect the first two picks as a declared synthetic policy, not Yahoo's list.
    protected={p['id'] for p in picks if p['team']==seat and p['pick']<=2*max(p['team'] for p in picks)}
    by_day=defaultdict(list);schedules=defaultdict(set)
    for g in season['games'].values():schedules[g['date']].update(g['teams'])
    for row in season['records']:by_day[row['date']].append(row)
    decision_times={}
    for g in season['games'].values():
        if 'start' in g:decision_times[g['date']]=min(decision_times.get(g['date'],g['start']),g['start'])
    days=sorted(schedules);weeks={};transactions=[];cooldown={};traces=[]
    conflicts={(c['game_id'],c['id']) for c in season['source_conflicts']}
    for index,day in enumerate(days):
        decision_at=decision_times.get(day,day)
        week=weeks.setdefault(week_key(day),{'skater':0.0,'goalie':0.0,'bench':0.0,'appearances':0,'adds':0,'source_conflicts':0})
        if stream and week['adds']<max_acquisitions:
            upcoming=[schedules[d] for d in days[index:] if week_key(d)==week_key(day)]
            base=weekly_value(own,forecasts,teams,upcoming,slots)
            # Shortlist by pre-outcome expected production on scheduled days.
            candidates=sorted((p for p in free if cooldown.get(p,'')<=day),
                key=lambda p:(sum(teams[p] in s for s in upcoming)*forecasts[p].rate*forecasts[p].games/82,p),reverse=True)[:12]
            best=None;gain=0
            for add in candidates:
                for drop in sorted(own-protected):
                    proposed=own-{drop}|{add}
                    if not valid_roster(proposed,forecasts,slots):continue
                    difference=weekly_value(proposed,forecasts,teams,upcoming,slots)-base
                    # Cost: 10% of positive rest-of-season production sacrificed.
                    cost=max(0,forecasts[drop].points-forecasts[add].points)*0.1
                    if difference-cost>gain+1:
                        gain=difference-cost;best=(add,drop)
            if best:
                add,drop=best;own.remove(drop);own.add(add);free.remove(add);free.add(drop)
                cooldown[drop]=(date.fromisoformat(day)+timedelta(days=waiver_days)).isoformat()
                week['adds']+=1;transactions.append({'date':day,'decision_at':decision_at,'add':add,'drop':drop,'estimated_net_gain':gain})
        selected=choose_daily(own,forecasts,teams,schedules[day],slots)
        traces.append({'date':day,'decision_at':decision_at,'selected':sorted(selected),'roster':sorted(own)})
        # All outcomes and team changes become visible only after the decision.
        for row in by_day[day]:
            if row['id'] in own:
                if row['id'] in selected:
                    week[row['kind']]+=row['points']
                    if row['kind']=='goalie' and row['appeared']:week['appearances']+=1
                    if (row['game_id'],row['id']) in conflicts:week['source_conflicts']+=1
                else:week['bench']+=row['points']
            if row['id'] in teams:teams[row['id']]=row['team']
    for w in weeks.values():
        w['lineup_points']=w['skater']+w['goalie']
        w['goalie_minimum_met']=w['appearances']>=3
        w['zero_goalie_penalty_scenario']=w['skater']+(w['goalie'] if w['goalie_minimum_met'] else 0)
        w['qualified_points']=w['zero_goalie_penalty_scenario']
    return {'weeks':weeks,'transactions':transactions,'daily_picks':traces,
            'lineup_points':sum(w['lineup_points'] for w in weeks.values()),
            'zero_goalie_penalty_scenario':sum(w['zero_goalie_penalty_scenario'] for w in weeks.values()),
            'goalie_minimum_failed_weeks':sum(not w['goalie_minimum_met'] for w in weeks.values()),
            'source_conflict_weeks':sum(bool(w['source_conflicts']) for w in weeks.values())}


def opportunity_evaluator(pool,players,previous_season,slots):
    """Marginal active-slot value using only the previous season's calendar."""
    forecasts={p.id:p for p in pool};schedules=defaultdict(set)
    for g in previous_season['games'].values():schedules[g['date']].update(g['teams'])
    def marginal(candidate,own_ids):
        value=candidate.rate*candidate.games/82;gain=0
        capacity=slots.get(candidate.position,0)
        if not capacity:return 0
        for teams in schedules.values():
            if players[candidate.id]['team'] not in teams:continue
            rivals=sorted((forecasts[p].rate*forecasts[p].games/82 for p in own_ids
                           if forecasts[p].position==candidate.position and players[p]['team'] in teams),reverse=True)
            displaced=rivals[capacity-1] if len(rivals)>=capacity else 0
            gain+=max(0,value-displaced)
        return gain
    return marginal


def run_year(seasons,target,config,team_counts=(14,),seed=0,market=None,waiver_days=2,max_acquisitions=4):
    if not team_counts or len(set(team_counts)) != len(team_counts) or any(t < 2 or t > 32 for t in team_counts):
        raise ValueError("Team counts must be unique integers from 2 through 32")
    players,history=prepare_history(seasons,target)
    if not history:raise ValueError('No pre-draft history')
    baseline=forecast(history,Model())
    models=[Model(),Model(20,.5,'points','cohort'),Model(0,0,'replacement'),Model(0,0,'usable')]
    all_runs=[]
    for model in models:
        pool=forecast(history,model);by_id={p.id:p for p in pool}
        for teams in team_counts:
            for seat in sorted({1,(teams+1)//2,teams}):
                utility=opportunity_evaluator(pool,players,seasons[target-1],dict(config.slots)) if model.strategy=='usable' else None
                picks=mock_draft(pool,baseline,dict(config.slots),teams,seat,seed,model.strategy,market=market,pick_value=utility)
                fixed=replay_season(seasons[target],picks,by_id,players,dict(config.slots),seat)
                # Separate same-draft management comparison, only on baseline.
                active=replay_season(seasons[target],picks,by_id,players,dict(config.slots),seat,stream=True,waiver_days=waiver_days,max_acquisitions=max_acquisitions) if model==models[0] else None
                all_runs.append({'model':asdict(model),'model_name':model.name,'teams':teams,'seat':seat,'seed':seed,
                                 'picks':picks,'fixed':fixed,'active':active})
    base={(r['teams'],r['seat']):r for r in all_runs if r['model']==asdict(models[0])}
    for r in all_runs:
        b=base[r['teams'],r['seat']]['fixed']
        r['paired_lineup_delta']=r['fixed']['lineup_points']-b['lineup_points']
        r['paired_penalty_scenario_delta']=r['fixed']['zero_goalie_penalty_scenario']-b['zero_goalie_penalty_scenario']
    summaries={m.name:{'mean_lineup_delta':mean(r['paired_lineup_delta'] for r in all_runs if r['model']==asdict(m)),
                       'mean_penalty_scenario_delta':mean(r['paired_penalty_scenario_delta'] for r in all_runs if r['model']==asdict(m))} for m in models}
    management=[r['active']['lineup_points']-r['fixed']['lineup_points'] for r in all_runs if r['active']]
    return {'ending_year':target,'season':seasons[target]['season'],'prior_player_pool':len(players),
            'summary':summaries,'mean_streaming_lineup_delta':mean(management),'runs':all_runs,
            'source_conflicts':len(seasons[target]['source_conflicts']),
            'market':'dated supplied export with synthetic fallback for unmatched players' if market else 'synthetic preferences, not observed ADP',
            'market_matched_players':len(set(players)&set(market or {})),
            'transaction_assumptions':{'waiver_days':waiver_days,'max_acquisitions':max_acquisitions,'initial_undrafted':'free by first season game'},
            'market_comparison':compare_market(baseline,market) if market else [],
            'warnings':seasons[target]['warnings']+[
                'Research comparison on reconstructed data; no automatic best-model selection or promotion',
                'Universe and eligibility from previous regular seasons; rookies and pre-draft injury/news changes not modeled',
                'Monday-Sunday weeks, no Yahoo playoff calendar or H2H opponents',
                'Team affiliation inferred from last observed game, updated only after each replayed day',
                'Minimum 3 goalie appearances; goalie points removed below minimum per Yahoo Help SLN6878',
                'Daily pre-first-game decisions; synthetic two-day dropped-player waiver cooldown, no competing claims',
                'Streaming limited by configured weekly budget and pre-draft universe; opponents retain drafted rosters',
                'Provider disagreements retained and flagged; affected totals are not verified official results']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history-dir',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--teams',nargs='+',type=int,default=[14],help='League sizes to compare (default: 14)')
    p.add_argument('--years',nargs='+',type=int,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--waiver-days',type=int,default=2);p.add_argument('--max-acquisitions',type=int,default=4)
    p.add_argument('--market-csv',type=Path);p.add_argument('--draft-date',type=date.fromisoformat)
    args=p.parse_args();config=load_config(args.config)
    if args.market_csv and (len(args.years)!=1 or not args.draft_date):p.error('Market requires one target year and explicit draft date')
    if len(set(args.teams)) != len(args.teams) or any(t < 2 or t > 32 for t in args.teams):p.error("Team counts must be unique integers from 2 through 32")
    years=range(min(args.years)-3,max(args.years)+1)
    seasons={y:json.loads((args.history_dir/f'history-{y}.json').read_text()) for y in years}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    summaries={}
    for y in args.years:
        market=load_market(args.market_csv,seasons[y]['season'],args.draft_date) if args.market_csv else None
        result=run_year(seasons,y,config,team_counts=tuple(args.teams),market=market,seed=args.seed,waiver_days=args.waiver_days,max_acquisitions=args.max_acquisitions)
        result['config_sha256']=hashlib.sha256(args.config.read_bytes()).hexdigest()
        result['history_sha256']={str(k):hashlib.sha256((args.history_dir/f'history-{k}.json').read_bytes()).hexdigest() for k in range(y-3,y+1)}
        path=args.output_dir/f'season-{y}.json'
        if path.exists():raise ValueError('Preserve prior experiments; use a new output directory')
        path.write_text(json.dumps(result))
        summaries[y]={k:result[k] for k in ('summary','prior_player_pool','mean_streaming_lineup_delta','source_conflicts')}
        print(y,summaries[y],flush=True)
    (args.output_dir/'summary.json').write_text(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
