"""Download published SportsDataverse season CSV releases, preserving receipts."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen,Request

DATASETS={'player_box':'nhl_player_boxscores','goalie_box':'nhl_goalie_boxscores','schedule':'nhl_schedules','scoring':'nhl_scoring','team_box':'nhl_team_boxscores','skater_box':'nhl_skater_boxscores'}


def fetch(directory,year,dataset):
    name=f'{"nhl_schedule" if dataset=="schedule" else dataset}_{year}.csv'
    path=directory/name
    if path.exists():
        receipt=json.loads(path.with_suffix('.metadata.json').read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['sha256']:
            raise ValueError('Cached download differs from its receipt')
        return path
    url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{DATASETS[dataset]}/{name}'
    with urlopen(Request(url,headers={'User-Agent':'FantasyHockeyGM-PersonalResearch/0.1'}),timeout=45) as response:
        raw=response.read(20000001)
    if len(raw)>20000000 or b',' not in raw.splitlines()[0]:raise ValueError('Invalid CSV response')
    directory.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)
    receipt={'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),
             'attribution':'SportsDataverse / fastRhockey','release_year_convention':'season ending year; verify against rows',
             'license_url':'https://github.com/sportsdataverse/sportsdataverse-data/blob/main/LICENSE'}
    path.with_suffix('.metadata.json').write_text(json.dumps(receipt,indent=2))
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--years',type=int,nargs='+',required=True);p.add_argument('--datasets',choices=DATASETS,nargs='+',default=list(DATASETS))
    a=p.parse_args()
    for year in a.years:
        for dataset in a.datasets:print(fetch(a.directory,year,dataset),flush=True)


if __name__=='__main__':main()
