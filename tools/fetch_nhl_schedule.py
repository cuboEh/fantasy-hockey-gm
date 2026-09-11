"""Cache public NHL website JSON, an undocumented endpoint without API SLA.

One request per team with a pause; reuse snapshots. No accounts or scraping.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from fantasy_hockey.providers.nhl_schedule import TEAMS, normalize_club_schedules


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists; use a new filename')
    a.directory.mkdir(parents=True,exist_ok=True)
    for team in TEAMS.values():
        path=a.directory/f'{team}.json'
        if path.exists():continue
        url=f'https://api-web.nhle.com/v1/club-schedule-season/{team}/20262027'
        with urlopen(Request(url,headers={'User-Agent':'FantasyHockeyGM-PersonalResearch/0.1'}),timeout=20) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Oversize response')
        payload=json.loads(raw)
        if not isinstance(payload.get('games'),list):raise ValueError('Unexpected schedule schema')
        saved={'source':url,'source_kind':'undocumented_public_endpoint','retrieved_at':datetime.now(timezone.utc).isoformat(),
               'sha256':hashlib.sha256(raw).hexdigest(),'payload':payload}
        with path.open('x') as out:json.dump(saved,out)
        print(team,flush=True);time.sleep(0.5)

    snapshots={team:json.loads((a.directory/f'{team}.json').read_text()) for team in TEAMS.values()}
    result=normalize_club_schedules(snapshots)
    with a.output.open('x') as out:json.dump(result,out,indent=2)
    print(f"Validated {len(result['games'])} games")


if __name__=='__main__':main()
