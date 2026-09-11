"""Audit and export an ID-matched workload review; no source access or board edits."""
import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from fantasy_hockey.workload_review import validate_review


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workloads',type=Path,required=True);p.add_argument('--board',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--as-of',type=date.fromisoformat,required=True)
    a=p.parse_args()
    if a.output_dir.exists():p.error('Use a new output directory')
    data=json.loads(a.workloads.read_text());board=json.loads(a.board.read_text())
    result=validate_review(data,a.as_of)
    players={g['id']:g for g in board['players'] if g['kind']=='goalie'}
    if set(players)!={g['id'] for g in data['goalies']}:raise ValueError('Review does not cover exactly the board goalie universe')
    if data['board_sha256']!=hashlib.sha256(a.board.read_bytes()).hexdigest():raise ValueError('Review board hash mismatch')
    for g in data['goalies']:
        original=players[g['id']]
        if original['team']!=g['team'] or original['points_per_game']!=g['rate']:raise ValueError('Review silently changed team or rate')
    result['workloads_sha256']=hashlib.sha256(a.workloads.read_bytes()).hexdigest()
    a.output_dir.mkdir(parents=True)
    (a.output_dir/'audit.json').write_text(json.dumps(result,indent=2))
    cols=['id','name','team','role','review_status','historical_projected_appearances','baseline_starts','downside_starts','health_status','review_by','source','fact']
    with (a.output_dir/'goalies.csv').open('x') as out:
        writer=csv.DictWriter(out,fieldnames=cols);writer.writeheader()
        for g in data['goalies']:writer.writerow({k:g['evidence'][k] if k in {'source','fact'} else g.get(k) for k in cols})
    lines=['# Complete goalie workload review','', 'Start counts are analyst scenarios, not reported forecasts. A reviewed role can remain uncertain.', '',
           '| Player | Team | Role | Baseline starts | Downside | Evidence |', '| --- | --- | --- | ---: | ---: | --- |']
    for g in data['goalies']:
        e=g['evidence'];lines.append(f"| {g['name']} | {g['team']} | {g['role']} | {g['baseline_starts']} | {g['downside_starts']} | [{e['date']}]({e['source']}) |")
    lines.extend(['','## Review notes',''])
    for g in data['goalies']:lines.append(f"- **{g['name']}**: {g['evidence']['fact']} Health: {g['health_status']}. Recheck by {g['review_by']}.")
    (a.output_dir/'review.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
