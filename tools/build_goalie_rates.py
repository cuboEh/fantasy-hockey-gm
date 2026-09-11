"""Build auditable starter and relief rates from existing local snapshots."""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from fantasy_hockey.goalie_rates import estimate_rates
from fantasy_hockey.config import load_config


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('history','goalie-box','config','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Use a new output path')
    with a.goalie_box.open() as f:boxes=list(csv.DictReader(f))
    result=estimate_rates(json.loads(a.history.read_text()),boxes,load_config(a.config).weights['goalie'],a.as_of)
    result['input_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.history,a.goalie_box,a.config)}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(f"Built {len(result['players'])} goalie rate records")


if __name__=='__main__':main()
