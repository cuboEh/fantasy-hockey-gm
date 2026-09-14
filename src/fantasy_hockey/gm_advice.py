"""Pure dated GM lineup and single-move comparisons. No roster writes or I/O."""

from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .gm_forecasts import forecast_points
from .gm_state import POSITIONS, inspect_snapshot, timestamp


def data(snapshot, name, fallback=None):
    value=(snapshot['inputs'].get(name) or {}).get('data')
    return fallback if value is None else value


def catalog(snapshot):
    players={p['id']:p for p in data(snapshot,'players',[])}
    players.update({p['id']:p for p in data(snapshot,'roster',[])})
    return players


def restrictions(snapshot, inspection, names):
    return [name.replace('_',' ')+': '+inspection['inputs'].get(name,{}).get('status','missing').replace('_',' ')
            for name in names if inspection['inputs'].get(name,{}).get('status')!='current']


def assign_all(players, slots, values, fixed, priorities=None):
    """Exact complete-roster matching; bench capacity and locked assignments matter.

    The state is slot occupancy. Ties preserve observed assignments then stable ID
    order. Every non-injury player must fit; negative points never create an
    imaginary extra bench slot.
    """
    positions=tuple(sorted(k for k,n in slots.items() if n and k not in ('IR','IR+')))
    capacity=tuple(slots[k] for k in positions)
    states={(0,)*len(positions):(Decimal(0),Decimal(0),0,())}
    for player in sorted(players,key=lambda p:p['id']):
        pid=player['id'];updated={}
        allowed={fixed[pid]} if pid in fixed else set(player['positions'] or [])|{'BN'}
        for used,(priority,value,changes,trace) in states.items():
            for i,pos in enumerate(positions):
                if pos not in allowed or used[i]>=capacity[i]:continue
                next_used=list(used);next_used[i]+=1;next_used=tuple(next_used)
                points=Decimal(str(values.get(pid,0))) if pos in POSITIONS else Decimal(0)
                extra=Decimal(str((priorities or {}).get(pid,0))) if pos in POSITIONS else Decimal(0)
                candidate=(priority+extra,value+points,changes-int(player.get('selected_position')!=pos),trace+((pid,pos),))
                if next_used not in updated or candidate[:3]>updated[next_used][:3]:updated[next_used]=candidate
        states=updated
        if not states:return None
    _,value,_,trace=max(states.values(),key=lambda v:v[:3])
    return {'points':float(value),'assignments':dict(trace)}


def game_projection(snapshot, player, games):
    forecast=next((r for r in data(snapshot,'forecasts',[]) if r['id']==player['id']),None)
    if forecast is None or 'rates' not in forecast:return None,'Numerical forecast missing',[]
    if forecast['model_role']!='working':return None,'Experimental forecast excluded from working advice',[]
    if forecast['kind']!=('goalie' if player['positions']==['G'] else 'skater'):
        return None,'Forecast kind differs from eligibility',[]
    ids={g['id'] for g in games}
    supplied={g['game_id'] for g in forecast['games']}
    if not ids<=supplied:return None,'Forecast does not cover these games',[]
    assumptions=[g for g in forecast['games'] if g['game_id'] in ids]
    if any(g['participation']=='scenario' for g in assumptions):
        return None,'Conditional scenario excluded from working advice',assumptions
    result=forecast_points(forecast,data(snapshot,'settings')['config']['scoring'][forecast['kind']],ids)
    return result,result['reason'],assumptions


def plan_day(snapshot, roster, day, now, *, new_player=None):
    settings=data(snapshot,'settings');slots=settings['config']['roster'];zone=ZoneInfo(settings['timezone'])
    games=[g for g in data(snapshot,'schedule',[]) if timestamp(g['starts_at'],'start').astimezone(zone).date()==day]
    values={};fixed={};issues=[];evidence={};scheduled=0;injured=[]
    is_today=day==now.astimezone(zone).date()
    for player in roster:
        pid=player['id'];position=player['selected_position']
        team_games=[g for g in games if player['nhl_team'] in g['teams']]
        started=any(timestamp(g['starts_at'],'start')<=now for g in team_games) if is_today else False
        if position in ('IR','IR+'):
            injured.append(pid)
            if player.get('injury_slots') is None or position not in player['injury_slots']:
                issues.append(player['name']+': injury-slot eligibility unverified; held in place')
            continue
        if not player['positions'] or not player['nhl_team']:
            return {'date':day.isoformat(),'status':'restricted','reasons':[player['name']+': eligibility or team unknown']}
        if position is None and pid!=new_player:
            return {'date':day.isoformat(),'status':'restricted','reasons':[player['name']+': actual lineup assignment unknown']}
        if started:
            fixed[pid]='BN' if pid==new_player and position is None else position
        future=[g for g in team_games if timestamp(g['starts_at'],'start')>now]
        scheduled+=len(future)
        if not future:
            values[pid]=0;continue
        projection,reason,assumptions=game_projection(snapshot,player,future)
        statuses={r['id']:r for r in data(snapshot,'player_status',[])}
        status=statuses.get(pid)
        envelope=snapshot['inputs']['player_status']
        fresh=(envelope['coverage']=='complete' and envelope['expires_at'] is not None
               and timestamp(envelope['observed_at'],'status')<=now<timestamp(envelope['expires_at'],'status'))
        if not fresh or status is None:
            reason='Current player-status evidence missing'
        elif status['confirmed'] and status['status'] in ('out','injured','inactive'):
            if projection and projection['expected_appearances']:
                reason='Forecast conflicts with confirmed unavailability'
        elif status['status'] not in ('available','healthy','active','unknown'):
            reason='Player status semantics unsupported'

        if reason:
            fixed[pid]=position;values[pid]=0
            issues.append(player['name']+': '+reason+'; assignment held, points excluded')
        else:
            values[pid]=projection['points'];evidence[pid]={**projection,'games':assumptions}
    regular=[p for p in roster if p['id'] not in injured]
    plan=assign_all(regular,slots,values,fixed)
    if plan is None:
        return {'date':day.isoformat(),'status':'restricted','reasons':['No complete legal assignment fits active and bench slots']}
    assignments={**plan['assignments'],**{p['id']:p['selected_position'] for p in roster if p['id'] in injured}}
    actual=sum(values.get(p['id'],0) for p in regular if p['selected_position'] in POSITIONS)
    active=[pid for pid,pos in assignments.items() if pos in POSITIONS]
    appearances=sum(evidence.get(pid,{}).get('expected_appearances',0) for pid in active
                    if next(p for p in roster if p['id']==pid)['positions']==['G'])
    used=Counter(assignments.values())
    gaps=[{'position':p,'open_slots':n-used[p]} for p,n in slots.items() if p in POSITIONS and n>used[p]]
    bench=[{'id':pid,'points':evidence[pid]['points'],'games':len(evidence[pid]['games'])}
           for pid,pos in assignments.items() if pos=='BN' and pid in evidence]
    no_game_slots=[]
    names={p['id']:p['name'] for p in roster}
    gap_explanations=[f"{day.isoformat()}: {g['open_slots']} {g['position']} slot(s) open in the points-first plan. "
                      + ('Review goalie qualification and its alternative.' if g['position']=='G' else 'No extra supported production fits this plan.')
                      for g in gaps]
    for pid in active:
        if pid in evidence:continue
        player=next(p for p in roster if p['id']==pid)
        team_games=[g for g in games if player['nhl_team'] in g['teams']]
        reason=('No team game in the supplied schedule' if not team_games else
                'Games already started; no remaining production counted' if all(timestamp(g['starts_at'],'start')<=now for g in team_games)
                else 'Projected workload or scoring inputs missing; production excluded')
        no_game_slots.append({'id':pid,'position':assignments[pid],'reason':reason})
        gap_explanations.append(f"{day.isoformat()}: {names[pid]} in {assignments[pid]}: {reason}.")
    for item in bench:
        if item['points']>0:
            gap_explanations.append(f"{day.isoformat()}: {names[item['id']]} has {item['games']} benched game(s), "
                                    f"{item['points']:.2f} projected points excluded by the full-roster assignment.")
    priorities={p['id']:evidence.get(p['id'],{}).get('expected_appearances',0)
                if p['positions']==['G'] else 0 for p in regular}
    alternative=assign_all(regular,slots,values,fixed,priorities)
    alt_assignments={**alternative['assignments'],**{p['id']:p['selected_position'] for p in roster if p['id'] in injured}}
    alt_points=sum(values.get(pid,0) for pid,pos in alt_assignments.items() if pos in POSITIONS)
    alt_appearances=sum(evidence.get(p['id'],{}).get('expected_appearances',0) for p in regular
                        if p['positions']==['G'] and alt_assignments[p['id']]=='G')
    alternative={'assignments':alt_assignments,'points':alt_points,'expected_goalie_appearances':alt_appearances,
        'point_cost':plan['points']-alt_points,'interpretation':'Maximum supported goalie exposure, then points; conditional opportunity, not guaranteed qualification'}
    changes=[{'id':p['id'],'name':p['name'],'from':p['selected_position'],'to':assignments[p['id']]}
             for p in roster if p['selected_position']!=assignments[p['id']]]
    return {'date':day.isoformat(),'status':'partial' if issues else ('change' if changes else 'no_change'),
        'assignments':assignments,'changes':changes,'locked_player_ids':sorted(fixed),'points':plan['points'],
        'actual_lineup_points':actual if is_today else None,'gain':plan['points']-actual if is_today else None,
        'baseline':'Exact legal points-first assignment; the working suggestion uses this same baseline',
        'scheduled_games':scheduled,'assignable_games':sum(len(evidence[pid]['games']) for pid in active if pid in evidence),
        'bench':bench,'gaps':gaps,'gap_explanations':gap_explanations,'active_slots_without_supported_future_game':no_game_slots,
        'injury_slot_players':injured,'goalie_expected_appearances':appearances,
        'goalie_negative_exposure':[pid for pid in active if pid in evidence and evidence[pid]['points']<0],
        'reasons':issues,'evidence':evidence,'goalie_alternative':alternative}


def lineups(snapshot, now, *, revision=0, last_error=None, roster=None, new_player=None):
    inspection=inspect_snapshot(snapshot,now,revision,last_error)
    reasons=restrictions(snapshot,inspection,('settings','roster','schedule','schedule_coverage','forecasts'))
    settings=data(snapshot,'settings',{});rules=settings.get('rules',{})
    if last_error:reasons.append('Last refresh failed or is incomplete; advice unavailable')
    for key in ('config','timezone','matchup'):
        if settings.get(key) is None:reasons.append(key+' is unknown')
    if rules.get('lineup_lock')!='daily_today':reasons.append('Only verified daily-today locks are supported')
    if rules.get('lock_benched_players') is None:reasons.append('Benched-player lock rule unknown')
    if reasons:return {'status':'restricted','reasons':reasons,'days':[],'state_key':inspection['state_key']}
    zone=ZoneInfo(settings['timezone']);today=now.astimezone(zone).date()
    matchup=settings['matchup'];end=date.fromisoformat(matchup['end'])
    if not date.fromisoformat(matchup['start'])<=today<=end:
        reasons.append('Supplied matchup does not contain today')
    if (end-today).days>30:reasons.append('Matchup exceeds supported 31-day planning horizon')
    observed=timestamp(snapshot['inputs']['roster']['observed_at'],'roster observation').astimezone(zone).date()
    if observed!=today:reasons.append('Actual lineup was not observed today')
    roster=roster if roster is not None else data(snapshot,'roster',[])
    coverage=data(snapshot,'schedule_coverage',{})
    start_at=datetime.combine(today,time(),zone);end_at=datetime.combine(end+timedelta(days=1),time(),zone)
    if (timestamp(coverage['start'],'coverage')>start_at or timestamp(coverage['end'],'coverage')<end_at
            or any(p['nhl_team'] not in coverage['teams'] for p in roster)):
        reasons.append('Schedule coverage does not establish the complete matchup for these teams')
    if reasons:return {'status':'restricted','reasons':reasons,'days':[],'state_key':inspection['state_key']}
    days=[plan_day(snapshot,roster,today+timedelta(days=i),now,new_player=new_player)
          for i in range((end-today).days+1)]
    supported=[d for d in days if d['status']!='restricted']
    minimum=rules.get('goalie_minimum');earned=None
    if (inspection['inputs'].get('goalie_results',{}).get('status')=='current'
            and rules.get('goalie_qualification')=='active_appearances'):
        games={g['id']:g for g in data(snapshot,'schedule',[])}
        earned=sum(r['qualified'] for r in data(snapshot,'goalie_results',[]) if r['game_id'] in games
                   and matchup['start']<=timestamp(games[r['game_id']]['starts_at'],'start').astimezone(zone).date().isoformat()<=matchup['end']
                   and timestamp(games[r['game_id']]['starts_at'],'start')<=now)
    expected=sum(d['goalie_expected_appearances'] for d in supported)
    return {'status':'restricted' if not supported else ('partial' if any(d['status'] in ('partial','restricted') for d in days) else 'supported'),
        'state_key':inspection['state_key'],'reasons':[], 'days':days,
        'remaining_points':sum(d['points'] for d in supported),
        'goalie':{'minimum':minimum,'confirmed_earned':earned,'future_expected':expected,
            'remaining_required':max(0,minimum-earned) if minimum is not None and earned is not None else None,
            'alternative_expected':sum(d['goalie_alternative']['expected_goalie_appearances'] for d in supported),
            'alternative_point_cost':sum(d['goalie_alternative']['point_cost'] for d in supported),
            'needs_review':minimum is None or earned is None or earned<minimum,
            'warning':'Expected appearances are conditional, not guaranteed qualification. Negative goalie exposure and unknown starts require review.'},
        'scope':'Remaining games only. Past or started games are locked and excluded from future point totals.'}


def compare_pickup(snapshot, now, candidate_id, drop_id=None, *, revision=0, last_error=None):
    inspection=inspect_snapshot(snapshot,now,revision,last_error)
    reasons=restrictions(snapshot,inspection,('availability','players'))
    players=catalog(snapshot);roster=data(snapshot,'roster',[]);own={p['id'] for p in roster}
    candidate=players.get(candidate_id);drop=next((p for p in roster if p['id']==drop_id),None)
    settings=data(snapshot,'settings',{});rules=settings.get('rules',{})
    availability=next((r for r in data(snapshot,'availability',[]) if r['id']==candidate_id),None)
    if candidate is None:reasons.append('Candidate identity/eligibility is not supplied')
    if candidate_id in own:reasons.append('Candidate is already on the roster')
    if availability is None or availability['state']=='unknown':reasons.append('Candidate availability is unknown')
    elif availability['state']=='owned':reasons.append('Candidate is owned by another team')
    elif availability['state']=='waivers':
        reasons.append('Waiver claim is conditional; refresh confirmed availability after clearance before evaluating an executable add')
    limit=rules.get('acquisition_limit');used=rules.get('acquisitions_used')
    if limit is None or used is None:reasons.append('Remaining acquisitions are unknown')
    elif used>=limit:reasons.append('No acquisitions remain this matchup')
    if drop_id and drop is None:reasons.append('Drop player is not on this roster')
    if drop and drop.get('can_drop') is not True:reasons.append('Drop permission / cannot-cut status is not verified')
    if drop and drop['selected_position'] in ('IR','IR+'):
        reasons.append('Dropping an injury-slot player does not establish a regular roster vacancy')
    if rules.get('waiver_mode')!='standard':reasons.append('Acquisition processing mode is unsupported or unknown')
    before=lineups(snapshot,now,revision=revision,last_error=last_error)
    if before['status'] not in ('supported',):reasons.append('Complete supported lineup valuation required for a pickup comparison')
    if (drop and before['days'] and drop_id in before['days'][0].get('locked_player_ids',[])
            and not (drop['selected_position']=='BN' and rules.get('lock_benched_players') is False)):
        reasons.append('Drop player is locked today')
    result={'status':'restricted','candidate_id':candidate_id,'drop_id':drop_id,'reasons':reasons,
            'state_key':inspection['state_key'],'keep_roster':before,'acquisition_cost':1,
            'effective_at':now.isoformat() if availability and availability['state']=='free_agent' else None,
            'waiver_clears_at':availability['waiver_clears_at'] if availability else None}
    if reasons:return result
    slots=settings['config']['roster'];regular=sum(p['selected_position'] not in ('IR','IR+') for p in roster)
    capacity=sum(n for pos,n in slots.items() if pos not in ('IR','IR+'))
    injury_slot=None
    if not drop and regular>=capacity:
        if rules.get('allow_direct_injury_slot_adds') is True:
            occupied=Counter(p['selected_position'] for p in roster)
            injury_slot=next((slot for slot in ('IR+','IR') if slot in (candidate.get('injury_slots') or [])
                              and occupied[slot]<slots.get(slot,0)),None)
        if injury_slot is None:
            result['reasons'].append('Roster is full; select a legal drop or supply verified eligibility for a vacant injury slot');return result
    replacement=deepcopy(candidate);replacement['selected_position']=injury_slot
    after_roster=[p for p in roster if p['id']!=drop_id]+[replacement]
    after=lineups(snapshot,now,revision=revision,last_error=last_error,roster=after_roster,new_player=candidate_id)
    if after['status']!='supported':
        result['reasons'].append('Resulting roster has unsupported inputs or cannot fit legal slots');result['resulting_roster']=after;return result
    gain=after['remaining_points']-before['remaining_points']
    result.update(status='comparison',resulting_roster=after,net_points=gain,
        added_usable_points=sum(d['evidence'].get(candidate_id,{}).get('points',0) for d in after['days']
                                if d['assignments'].get(candidate_id) in POSITIONS),
        lost_usable_points=sum(d['evidence'].get(drop_id,{}).get('points',0) for d in before['days']
                               if d['assignments'].get(drop_id) in POSITIONS),
        rest_of_season=None,decision='keep_roster' if gain<=0 else 'review',
        explanation='Keep roster has equal or higher projected production.' if gain<=0 else
            'Projected remaining-matchup gain; rest-of-season opportunity cost is unverified, so no drop recommendation is issued.')
    season_end=(settings.get('league_details') or {}).get('season_end')
    coverage=data(snapshot,'schedule_coverage',{})
    if season_end:
        zone=ZoneInfo(settings['timezone']);last=date.fromisoformat(season_end)
        start=now.astimezone(zone).date()
        boundary=datetime.combine(last+timedelta(days=1),time(),zone)
        if (0<=(last-start).days<=366 and timestamp(coverage['end'],'coverage')>=boundary
                and all(p['nhl_team'] in coverage['teams'] for p in after_roster)):
            old_days=[plan_day(snapshot,roster,start+timedelta(days=i),now) for i in range((last-start).days+1)]
            new_days=[plan_day(snapshot,after_roster,start+timedelta(days=i),now,new_player=candidate_id)
                      for i in range((last-start).days+1)]
            if all(d['status'] in ('change','no_change') for d in old_days+new_days):
                old_points=sum(d['points'] for d in old_days);new_points=sum(d['points'] for d in new_days)
                result['rest_of_season']={'through':season_end,'keep_points':old_points,'move_points':new_points,
                    'net_points':new_points-old_points,'overlaps_matchup':True,
                    'assumption':'Current roster management and supplied dated workload throughout; not added to matchup gain'}
                if gain>0 and new_points>=old_points:
                    result.update(decision='consider',explanation='Both remaining-matchup and rest-of-season usable production improve or hold under supplied assumptions. Review goalie qualification before manual execution.')
                elif gain>0:
                    result.update(decision='keep_roster',explanation='Short-term gain sacrifices projected rest-of-season usable production.')
    result['goalie_impact']={'before':before['goalie'],'after':after['goalie']}
    if result['decision']=='consider' and after['goalie']['needs_review']:
        result.update(decision='review',explanation='Projected gain requires review of unresolved goalie qualification before considering the move.')
    return result
