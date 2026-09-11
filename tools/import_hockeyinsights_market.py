"""Extract one published ranking series from a permitted Hockey Insights snapshot.

This is a provider-reported ranking proxy, never Yahoo ADP or a blended forecast.
"""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from fantasy_hockey.scoring import number


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--series',choices=['espn','nhl','dfo','cbs'],default='espn')
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();data=json.loads(a.input.read_text())
    if data['meta']['season']!='2026-27' or date.fromisoformat(data['meta']['generated'])>a.as_of:
        p.error('Source season/date incompatible')
    if a.output.exists() or a.output.with_suffix('.metadata.json').exists():p.error('Preserve existing imports; use new output')
    rows=[];seen=set()
    for group in ('players','goalies','consensusOnly'):
        for player in data[group]:
            value=(player.get('consensus') or {}).get(a.series)
            if value is None:continue
            pid=f"nhl:{player['id']}"
            if pid in seen or number(value,'rank')<=0:raise ValueError('Duplicate identity or invalid rank')
            seen.add(pid)
            rows.append({'id':pid,'season':'2026-27','as_of':data['meta']['generated'],
                         'source':f'Hockey Insights published {a.series.upper()} rank proxy (not Yahoo ADP)',
                         'metric':'rank','value':value})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','season','as_of','source','metric','value'])
        writer.writeheader();writer.writerows(rows)
    a.output.with_suffix('.metadata.json').write_text(json.dumps({'rows':len(rows),
        'source':'https://hockeyinsights.ca/data/fantasy_2027.json','terms':'https://hockeyinsights.ca/opendata/',
        'sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'series':a.series,
        'warnings':['Source snapshot date, not independent verification of each ranking publication date',
                    'Secondary provider ranking, not Yahoo draft-room order or observed ADP',
                    'Missing ranks stay missing; no average of differently covered ranking lists']},indent=2))
    print(f'Imported {len(rows)} {a.series.upper()} proxy ranks; not Yahoo ADP.')


if __name__=='__main__':main()
