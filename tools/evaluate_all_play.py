"""Score locked drafts against every simulated opponent each week, without a matchup schedule."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean

from fantasy_hockey.backtest import Model, forecast
from fantasy_hockey.config import load_config
from fantasy_hockey.seasonlab import prepare_history, replay_season


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directories',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Use a new output path')
    config=load_config(Path('config.local.toml'))
    results=[];hashes={}
    for directory in a.directories:
        manifest_path=directory/'manifest.json'
        manifest=json.loads(manifest_path.read_text())
        if not (directory/'summary.json').exists():
            raise ValueError('Draft study is not complete: '+str(directory))
        hashes[str(manifest_path)]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        for name,expected in manifest['input_sha256'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected:
                raise ValueError('Historical input changed since the locked draft run: '+name)
        for path in sorted(directory.glob('season-*.json')):
            hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
            year=int(path.stem.split('-')[1])
            seasons={y:json.loads(Path(f'var/history-{y}.json').read_text()) for y in range(max(2013,year-3),year+1)}
            metadata,history=prepare_history(seasons,year)
            forecasts={p.id:p for p in forecast(history,Model())}
            records=defaultdict(list)
            for row in seasons[year]['records']:records[row['id']].append(row)
            for run in json.loads(path.read_text())['runs']:
                weeks={}
                for seat in range(1,15):
                    ids=[r['id'] for r in run['picks'] if r['team']==seat]
                    season={**seasons[year],'records':[r for pid in ids for r in records[pid]]}
                    weeks[seat]=replay_season(season,run['picks'],forecasts,metadata,dict(config.slots),seat)['weeks']
                own=weeks[run['seat']];scores={}
                for seat,opponent in weeks.items():
                    if seat==run['seat']:continue
                    for week,aweek in own.items():
                        bweek=opponent[week]
                        if aweek['source_conflicts'] or bweek['source_conflicts']:continue
                        left=aweek['zero_goalie_penalty_scenario'];right=bweek['zero_goalie_penalty_scenario']
                        scores[f'{seat}:{week}']=1.0 if left>right else .5 if left==right else 0.0
                results.append({'year':year,'policy':run['policy'],'seat':run['seat'],
                                'seed':manifest['seed'],'style':run['style'],
                                'clean_pair_weeks':len(scores),'_scores':scores})
            print('Scored all-play',year,flush=True)
    groups=defaultdict(list)
    for row in results:groups[(row['year'],row['seat'],row['seed'],row['style'])].append(row)
    for group in groups.values():
        common=set.intersection(*(set(row['_scores']) for row in group))
        for row in group:
            row['common_clean_pair_weeks']=len(common)
            row['all_play_fraction']=mean(row['_scores'][key] for key in common) if common else None
            del row['_scores']
    summary={policy:mean(r['all_play_fraction'] for r in results if r['policy']==policy and r['all_play_fraction'] is not None)
             for policy in sorted({r['policy'] for r in results})}
    hashes[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output={'rows':results,'summary':summary,'input_sha256':hashes,
            'warning':'Synthetic all-play diagnostic: every opponent each week, ties count half. No real matchup schedule, streaming, playoffs or league-win probability. Uses common conflict-free opponent/week pairs across policies in each scenario.'}
    with a.output.open('x') as f:json.dump(output,f,indent=2)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
