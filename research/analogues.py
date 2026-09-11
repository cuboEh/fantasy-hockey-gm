"""Chronological historical analogues, not injury diagnoses or causal trade effects."""
from collections import defaultdict
from statistics import mean
from math import sqrt


def summarize(season):
    groups=defaultdict(list)
    for row in season['records']:
        if row['appeared']:groups[row['id']].append(row)
    result={}
    for pid,rows in groups.items():
        rows.sort(key=lambda r:(r['date'],r['game_id']))
        last=rows[-1];opportunities=season['team_games'][last['team']]
        gp=len(rows);points=sum(r['points'] for r in rows)
        result[pid]={'id':pid,'name':last['name'],'kind':last['kind'],'position':last['position'],
                     'group':'G' if last['kind']=='goalie' else ('D' if last['position']=='D' else 'F'),
                     'games':gp*82/opportunities,'points':points*82/opportunities,'rate':points/gp,
                     'teams_changed':len({r['team'] for r in rows})>1}
    return result


def candidates(annual, target):
    """Features use only completed seasons before target, including a missing-year flag."""
    prior={y:rows for y,rows in annual.items() if target-3<=y<target}
    ids={pid for rows in prior.values() for pid in rows};result=[]
    for pid in sorted(ids):
        lines=sorted(((y,rows[pid]) for y,rows in prior.items() if pid in rows),reverse=True)
        latest_year,latest=lines[0];previous=lines[1][1] if len(lines)>1 else latest
        weights=[(1/3)**i for i in range(len(lines))];mass=sum(weights)
        games=min(82,sum(w*r['games'] for w,(_,r) in zip(weights,lines))/mass)
        rate=sum(w*r['rate'] for w,(_,r) in zip(weights,lines))/mass
        scale=5 if latest['group']=='G' else 3
        features=[latest['games']/20,latest['rate']/scale,
                  (latest['games']-previous['games'])/20,
                  (latest['rate']-previous['rate'])/scale,
                  float(latest['teams_changed']),float(target-1-latest_year),float(len(lines)==1)]
        result.append({**latest,'target':target,'features':features,'baseline_games':games,
                       'baseline_rate':rate,'baseline_points':games*rate})
    return result


def examples(annual, first=2016, last=2026):
    result=[]
    for target in range(first,last+1):
        if target not in annual:continue
        for c in candidates(annual,target):
            actual=annual[target].get(c['id'])
            result.append({**c,'actual_games':actual['games'] if actual else 0,
                           'actual_points':actual['points'] if actual else 0,
                           'actual_rate':actual['rate'] if actual else None})
    return result


def predict(candidate, training, k=40):
    if k<1:raise ValueError('Positive neighbor count required')
    pool=[r for r in training if r['target']<candidate['target'] and r['id']!=candidate['id'] and r['group']==candidate['group']]
    distances=sorted(((sqrt(sum((a-b)**2 for a,b in zip(candidate['features'],r['features']))),r)
                      for r in pool),key=lambda pair:(pair[0],pair[1]['target'],pair[1]['id']))[:k]
    neighbors=[r for _,r in distances]
    if len(neighbors)<10:
        return {'games':candidate['baseline_games'],'rate':candidate['baseline_rate'],
                'points':candidate['baseline_points'],'workload_points':candidate['baseline_points'],
                'neighbors':[],'fallback':True}
    # Fixed before evaluation: shrink analogue residuals toward the baseline.
    strength=len(neighbors)/(len(neighbors)+40)
    games=max(0,min(82,candidate['baseline_games']+strength*mean(r['actual_games']-r['baseline_games'] for r in neighbors)))
    returning=[r for r in neighbors if r['actual_games']>=20 and r['actual_rate'] is not None]
    rate=candidate['baseline_rate']
    if len(returning)>=10:
        rate+=len(returning)/(len(returning)+40)*mean(r['actual_rate']-r['baseline_rate'] for r in returning)
    return {'games':games,'rate':rate,'points':games*rate,'workload_points':games*candidate['baseline_rate'],
            'neighbors':[{'id':r['id'],'name':r['name'],'target':r['target'],'distance':d,
                          'actual_games':r['actual_games'],'actual_points':r['actual_points']} for d,r in distances],
            'fallback':False}
