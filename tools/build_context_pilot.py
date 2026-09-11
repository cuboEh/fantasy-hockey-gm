"""Build an explicit four-case pilot from existing snapshots and dated research.

Parameter choices are analyst scenarios. They are neither calibrated nor reported
by the cited news sources. Outputs stay private and never replace the draft board.
"""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from collections import defaultdict
from fantasy_hockey.board import read_json,dump_json


def conditional_rates(history, goalie_csv, ids, as_of):
    records={(r['game_id'],r['id']):r for r in history['records'] if r['id'] in ids}
    groups=defaultdict(list);seen=set()
    with goalie_csv.open() as stream:
        for row in csv.DictReader(stream):
            if row['player_id'] not in ids or row['game_id'][4:6]!='02':continue
            key=(row['game_id'],row['player_id'])
            if key in seen:raise ValueError('Duplicate goalie game')
            seen.add(key)
            record=records.get(key)
            if record is None:raise ValueError('Missing normalized goalie outcome')
            if date.fromisoformat(record['date'])>as_of:raise ValueError('Future goalie outcome')
            if not record['appeared']:continue
            if row['starter'] not in ('true','false'):raise ValueError('Unknown starter status')
            groups[(row['player_id'],row['starter']=='true')].append(record['stats'])
    results={}
    for pid in ids:
        rates={}
        for starter,label in ((True,'start'),(False,'relief')):
            lines=groups[pid,starter];rates[label+'_sample']=len(lines)
            if not lines and starter:raise ValueError('Missing starts')
            rates['per_'+label]={k:sum(float(r[k]) for r in lines)/len(lines) for k in ('wins','goals_against','saves','shutouts')} if lines else None
        results['nhl:'+pid]={**rates,'source':'SportsDataverse published goalie boxes joined to normalized game outcomes',
                             'season':history['season'],'as_of':as_of.isoformat(),
                             'starter_input_sha256':hashlib.sha256(goalie_csv.read_bytes()).hexdigest(),
                             'warning':'Source conflicts retained; relief samples small. Prior regular season only.'}
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',type=Path,required=True);p.add_argument('--history',type=Path,required=True)
    p.add_argument('--goalie-box',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Use a new output path')
    board=read_json(a.board);players={p['id']:p for p in board['players']}
    today=date(2026,9,10)
    if board['season']!='2026-27':raise ValueError('Pilot assumptions are for 2026-27 only')
    evidence={
      'brady':{'date':'2026-06-23','fact':'Team article discusses a possible Barkov-Reinhart line.','source':'https://www.nhl.com/panthers/news/brady-tkachuk-fits-into-the-puzzle-for-the-panthers'},
      'barkov':{'date':'2026-09-09','fact':'Reports healthy ahead of camp.','source':'https://www.nhl.com/news/healthy-aleksander-barkov-raring-to-go-for-panthers-after-knee-injury'},
      'jarvis':{'date':'2026-06-27','fact':'Recovery estimated at four to six months after shoulder surgery.','source':'https://www.nhl.com/news/seth-jarvis-to-miss-beginning-of-2026-2027-season-for-hurricanes-after-shoulder-surgery'},
      'wild':{'date':'2026-08-14','fact':'Gustavsson recovering from hip surgery; Wallstedt could lead initially, with Pickard backing up.','source':'https://frontend.d3.nhle.com/news/topic/32-in-32/minnesota-wild-three-questions-for-2026-27-season-32-in-32'}}
    skaters=[]
    def add(pid,name,phases,assumptions,key,confirmation):
        skaters.append({'id':pid,'name':name,'phases':phases,'assumptions':assumptions,
                        'evidence':[evidence[key]],'confirmation_needed':confirmation,'review_by':'2026-09-12'})
    games=players['nhl:8480801']['projected_games']
    for name,factors,reason in [
        ('crowded deployment',{'goals':.95,'assists':1,'shots_on_goal':.90,'power_play_points':.80},'Hold appearances/hits fixed; test 10% fewer shots, 5% fewer goals and 20% fewer PPP, with assists unchanged.'),
        ('role retained',{},'Keep historical per-appearance rates and workload. No automatic trade penalty.'),
        ('productive top line',{'goals':1.05,'assists':1.10,'power_play_points':1.10},'Hold shots/hits/workload fixed; test 5% more goals and 10% more assists/PPP from improved conversion/playmaking.')]:
        add('nhl:8480801',name,[{'appearances':games,'rate_factors':factors}],reason,'brady','Confirm actual linemates and PP-unit deployment. Stat factors are analyst choices, not inferred coaching commitments.')
    offense={'goals':.85,'assists':.85,'shots_on_goal':.85,'power_play_points':.85}
    for name,phases,reason in [
        ('limited return',[{'appearances':20,'rate_factors':offense},{'appearances':40}], '60 appearances; first 20 at 85% historical offensive rates. Hits/plus-minus unchanged. Stress case, not prognosis.'),
        ('healthy regular',[{'appearances':72}], '72 appearances at historical rates; explicit working assumption, not a medically certified workload.'),
        ('durable return',[{'appearances':80}], '80 appearances at historical rates; no additional recovery or teammate bonus.')]:
        add('nhl:8477493',name,phases,reason,'barkov','Verify camp participation and normal minutes; separate durability from effectiveness after a season-long absence.')
    for name,missed,ramp in [('longer absence',36,.80),('intermediate absence',24,.90),('shorter absence',12,1)]:
        gp=(84-missed)*.95;first=min(gp,10)
        factors={k:ramp for k in ('goals','assists','shots_on_goal','power_play_points')}
        add('nhl:8482093',name,[{'appearances':first,'rate_factors':factors},{'appearances':gp-first}],
            f'{missed} early team games missed is an analyst exposure assumption, not a schedule-derived return date; 95% availability thereafter, first ten appearances at {ramp:.0%} offensive rates. Replace historical GP rather than subtracting absence twice.',
            'jarvis','Refresh recovery report and map a supported return window onto the actual schedule before selecting a case. IR replacement value remains separate.')
    goalies=[]
    for name,w,g,o in [('Gustavsson reclaims lead',38,40,6),('shared workload after recovery',46,30,8),('Wallstedt retains lead',56,20,8)]:
        goalies.append({'team':'MIN','name':name,'starts':{'nhl:8482661':w,'nhl:8479406':g,'other':o},
                        'relief_appearances':{'nhl:8482661':2,'nhl:8479406':2},
                        'assumptions':f'{w}/{g}/{o} starts for Wallstedt/Gustavsson/reserve goalies, totaling 84. Two relief appearances each for the named goalies. Keep prior conditional start/relief rates fixed. These are conditional allocations, not reported coach plans.',
                        'evidence':[evidence['wild']],'review_by':'2026-09-12',
                        'confirmation_needed':'Verify Gustavsson clearance, preseason rotation and Pickard role. Joint allocation must be revised if goalie identity/team changes.'})
    history=read_json(a.history)
    if history['season']!='20252026':raise ValueError('Pilot requires previous regular season')
    payload={'season':'2026-27','prior_season':'20252026','skaters':skaters,'goalie_teams':goalies,
             'goalie_rates':conditional_rates(history,a.goalie_box,{'8482661','8479406'},today),
             'history_sha256':hashlib.sha256(a.history.read_bytes()).hexdigest(),
             'history_source_conflicts':len(history['source_conflicts'])}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(dump_json(payload));print(a.output)


if __name__=='__main__':main()
