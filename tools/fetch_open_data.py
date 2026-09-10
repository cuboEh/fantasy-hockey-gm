"""Fetch the explicitly published Hockey Insights file into a new local snapshot.

Usage: uv run python tools/fetch_open_data.py snapshots/YYYY-MM-DD/hockeyinsights
Existing snapshots are never overwritten. No account or API credentials needed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

URL = 'https://hockeyinsights.ca/data/fantasy_2027.json'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    path=args.directory/'fantasy_2027.json'
    metadata_path=args.directory/'metadata.json'
    if path.exists() or metadata_path.exists():
        parser.error('Snapshot exists; use a new dated directory to preserve history')
    with urlopen(Request(URL,headers={'User-Agent':'FantasyHockeyGM-PersonalResearch/0.1'}),timeout=30) as response:
        content=response.read(5_000_001)
    if len(content)>5_000_000:
        raise ValueError('Unexpected response size')
    data=json.loads(content)
    if not all(key in data for key in ['meta','players','goalies','consensusOnly']):
        raise ValueError('Unexpected source schema')
    metadata={'source':URL,'attribution':'Hockey Insights (hockeyinsights.ca)',
              'terms_url':'https://hockeyinsights.ca/opendata/',
              'retrieved_at':datetime.now(timezone.utc).isoformat(),
              'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)}
    args.directory.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(content)
    with metadata_path.open('x') as stream:json.dump(metadata,stream,indent=2)
    print(path)


if __name__=='__main__':main()
