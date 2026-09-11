"""Score synthetic round-robin matchups for fixed vs active baseline rosters.

No Yahoo matchup schedule is inferred. Source-conflict weeks are reported and
excluded from the clean-data W/L/T comparison. No playoff results are claimed.
"""
import argparse
import json
from pathlib import Path
from fantasy_hockey.backtest import Model,forecast
from fantasy_hockey.config import load_config
from fantasy_hockey.seasonlab import prepare_history,replay_season


def rounds(teams):
    ring=list(range(1,teams+1))
    if teams%2:ring.append(None)
    result=[]
    for _ in range(len(ring)-1):
        result.append({a:b for x,y in zip(ring[:len(ring)//2],reversed(ring[len(ring)//2:])) for a,b in ((x,y),(y,x)) if a is not None})
        ring=[ring[0],ring[-1]]+ring[1:-1]
    return result


def compare(own,opponents,seat,teams):
    schedule=rounds(teams);record={'wins':0,'losses':0,'ties':0,'byes':0,'conflict_weeks_excluded':0};weeks=[]
    for i,(key,result) in enumerate(sorted(own['weeks'].items())):
        opponent=schedule[i%len(schedule)][seat]
        if opponent is None:record['byes']+=1;continue
        other=opponents[opponent]['weeks'][key]
        if result['source_conflicts'] or other['source_conflicts']:
            record['conflict_weeks_excluded']+=1;continue
        difference=result['zero_goalie_penalty_scenario']-other['zero_goalie_penalty_scenario']
        outcome='wins' if difference>1e-8 else 'losses' if difference< -1e-8 else 'ties'
        record[outcome]+=1;weeks.append({'week':key,'opponent':opponent,'point_difference':difference,'outcome':outcome})
    return {'record':record,'weeks':weeks}


def common_weeks(fixed,active):
    """Compare identical evaluable weeks, not two differently filtered records."""
    common={w['week'] for w in fixed['weeks']}&{w['week'] for w in active['weeks']}
    for side in (fixed,active):
        previous=len(side['weeks'])
        side['weeks']=[w for w in side['weeks'] if w['week'] in common]
        side['record']['conflict_weeks_excluded']+=previous-len(side['weeks'])
        for outcome in ('wins','losses','ties'):
            side['record'][outcome]=sum(w['outcome']==outcome for w in side['weeks'])
    return fixed,active


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for x in ('study-dir','history-dir','config','output'):p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args();config=load_config(a.config);results=[]
    for path in sorted(a.study_dir.glob('season-*.json')):
        report=json.loads(path.read_text());year=report['ending_year']
        seasons={y:json.loads((a.history_dir/f'history-{y}.json').read_text()) for y in range(year-3,year+1)}
        players,history=prepare_history(seasons,year);pool={p.id:p for p in forecast(history,Model())}
        for run in report['runs']:
            if not run['active']:continue
            opponents={seat:replay_season(seasons[year],run['picks'],pool,players,dict(config.slots),seat)
                       for seat in range(1,run['teams']+1) if seat!=run['seat']}
            fixed,active=common_weeks(compare(run['fixed'],opponents,run['seat'],run['teams']),compare(run['active'],opponents,run['seat'],run['teams']))
            results.append({'year':year,'teams':run['teams'],'seat':run['seat'],
                            'fixed':fixed,'active':active})
        print('Scored hypothetical matchups',year,flush=True)
    if a.output.exists():raise ValueError('Use a new output file to preserve prior results')
    a.output.write_text(json.dumps({'results':results,'warnings':['Synthetic round-robin opponents, not historical Yahoo matchups',
        'Opponents do not stream; acquisition competition and true playoff rules absent',
        'Conflict weeks excluded, so records are not full-season official results']},indent=2))


if __name__=='__main__':main()
