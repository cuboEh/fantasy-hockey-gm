"""Normalize published SportsDataverse records, rejecting unjoinable history."""
from collections import Counter,defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .scoring import score


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def assist_ids(value):
    if not value or value in {'null','[]'}:return []
    decoded=json.loads(value)
    if isinstance(decoded,list):return [str(x['playerId']) for x in decoded]
    # Some published older CSVs contain a quoted Polars Series rendering.
    if isinstance(decoded,str) and 'Series:' in decoded and 'struct[' in decoded:
        matches=re.findall(r'\{(\d+),\{',decoded.replace('\\"','"'))
        count=re.search(r'shape: \((\d+),\)',decoded)
        if count and int(count[1])==len(matches) and len(matches)<=2:return matches
    raise ValueError('Unsupported assist serialization')


def seconds(value):
    m,s=map(int,value.split(':'))
    if m<0 or not 0<=s<60:raise ValueError('Invalid ice time')
    return 60*m+s


def normalize(directory, ending_year, weights):
    paths={kind:directory/f'{kind}_{ending_year}.csv' for kind in ('skater_box','goalie_box','scoring','nhl_schedule')}
    rows={k:read_csv(p) for k,p in paths.items()}
    schedule={r['game_id']:r for r in rows['nhl_schedule'] if r['game_type']=='R'}
    if not schedule or any(r['game_state'] not in {'OFF','FINAL'} for r in schedule.values()):
        raise ValueError('Incomplete regular-season schedule')
    expected_season=f'{ending_year-1}{ending_year}'
    if any(r['season_full']!=expected_season for r in schedule.values()):raise ValueError('Season identity mismatch')
    games={};team_games=Counter()
    for gid,r in schedule.items():
        start=datetime.fromisoformat(r['game_time'].replace('Z','+00:00'))
        games[gid]={'id':gid,'date':start.astimezone(ZoneInfo('America/Edmonton')).date().isoformat(),
                    'start':start.isoformat(),'teams':[r['home_team_abbr'],r['away_team_abbr']]}
        team_games.update(games[gid]['teams'])
    goals=Counter();assists=Counter();ppp=Counter();team_goals=Counter();event_ids=set()
    for r in rows['scoring']:
        gid=r['game_id']
        if gid not in games or r['period_type']=='SO':continue
        key=(gid,r['eventId'])
        if key in event_ids:raise ValueError(f'Duplicate scoring event {key}')
        event_ids.add(key)
        scorer=str(r['playerId']);helpers=assist_ids(r['assists'])
        if len(helpers)!=len(set(helpers)) or scorer in helpers:raise ValueError('Invalid assists')
        goals[gid,scorer]+=1
        for identity in helpers:assists[gid,identity]+=1
        if r['strength']=='pp':
            for identity in [scorer]+helpers:ppp[gid,identity]+=1
        team_goals[gid,r['teamAbbrev.default']]+=1
    records=[];conflicts=[];seen=set();coverage=defaultdict(set);appearing_goalies=Counter()
    for r in rows['goalie_box']:
        if r['game_id'] in games and seconds(r['toi'])>0:appearing_goalies[r['game_id'],r['team_abbrev']]+=1
    for kind,key in [('skater','skater_box'),('goalie','goalie_box')]:
        for r in rows[key]:
            gid=r['game_id']
            if gid not in games:continue
            identity=r['player_id'];team=r['team_abbrev']
            if team not in games[gid]['teams']:raise ValueError('Boxscore team differs from schedule')
            unique=(gid,identity)
            if unique in seen:raise ValueError(f'Duplicate player game {unique}')
            seen.add(unique);coverage[gid,kind].add(team)
            appeared=seconds(r['toi'])>0
            if kind=='skater':
                if int(r['goals'])!=goals[unique] or int(r['assists'])!=assists[unique]:
                    conflicts.append({'game_id':gid,'id':identity,'issue':'scoring events and boxscore disagree; counts retained with derived PPP flagged'})
                stats={s:int(r[s]) for s in ('goals','assists','plus_minus','shots_on_goal','hits')}
                stats['power_play_points']=ppp[unique]
                pos={'L':'LW','R':'RW'}.get(r['position'],r['position'])
            else:
                opposition=next(t for t in games[gid]['teams'] if t!=team)
                stats={'wins':int(r['decision']=='W'),'goals_against':int(r['goals_against']),
                       'saves':int(r['saves']),
                       'shutouts':int(appeared and appearing_goalies[gid,team]==1 and team_goals[gid,opposition]==0)}
                if int(r['shots_against'])!=stats['saves']+stats['goals_against']:
                    conflicts.append({'game_id':gid,'id':identity,'issue':'goalie shots/saves/GA disagree; provider counts retained'})
                pos='G'
            if not appeared and any(stats.values()):
                conflicts.append({'game_id':gid,'id':identity,'issue':'zero ice time with scoring stats; appearance inferred'})
                appeared=True
            points=float(score(kind,stats,weights[kind]).total)
            records.append({'id':identity,'name':r['player_name'],'kind':kind,'position':pos,'team':team,
                            'game_id':gid,'date':games[gid]['date'],'appeared':appeared,'stats':stats,'points':points})
    for gid,g in games.items():
        if any(coverage[gid,k]!=set(g['teams']) for k in ('skater','goalie')):raise ValueError(f'Missing game coverage {gid}')
    return {'ending_year':ending_year,'season':expected_season,'games':games,'team_games':dict(team_games),'records':records,
            'source_conflicts':conflicts,
            'provenance':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},
            'warnings':['Reconstructed historical dataset, not archived pre-draft Yahoo eligibility',
                        'PPP derived from credited scoring events; shutouts from no opposing non-shootout goals and one appearing goalie',
                        'Schedule reflects final actual dates, not original publication or postponement knowledge']}


def main():
    import argparse
    from .config import load_config
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--years',type=int,nargs='+',required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();config=load_config(a.config);a.output_dir.mkdir(parents=True,exist_ok=True)
    report={}
    for year in a.years:
        path=a.output_dir/f'history-{year}.json'
        if path.exists():raise ValueError('Preserve normalized history; choose a new output directory')
        result=normalize(a.directory,year,config.weights)
        result['config_sha256']=hashlib.sha256(a.config.read_bytes()).hexdigest()
        path.write_text(json.dumps(result))
        report[year]={'games':len(result['games']),'records':len(result['records']),'source_conflicts':len(result['source_conflicts'])}
        print(year,report[year],flush=True)
    (a.output_dir/'coverage.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
