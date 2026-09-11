"""Attach observed outcomes in a separate artifact; never mutate pre-draft labels."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from fantasy_hockey.context_cases import validate_cases
from fantasy_hockey.board import dump_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=Path,required=True);p.add_argument('--history',type=Path,required=True)
    p.add_argument('--goalie-box',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Use new outcome artifact')
    cases=validate_cases(json.loads(a.cases.read_text())['cases']);history=json.loads(a.history.read_text())
    starts={};seen=set()
    with a.goalie_box.open() as stream:
        for row in csv.DictReader(stream):
            if row['game_id'][4:6]!='02':continue
            if row['season']!=history['season']:raise ValueError('Goalie outcome season mismatch')
            key=(row['game_id'],row['player_id'])
            if key in seen:raise ValueError('Duplicate goalie game')
            seen.add(key)
            label=row['starter'].strip().lower()
            if label not in {'true','false'}:raise ValueError('Missing starter label')
            starts[key]=label=='true'
    outcomes=[]
    for case in cases:
        if case['season']!=history['season']:raise ValueError('Outcome season does not match case')
        if min(g['date'] for g in history['games'].values())<=case['cutoff']:
            raise ValueError('Case cutoff must precede target-season games')
        pid=case['player_id'][4:];rows=[r for r in history['records'] if r['id']==pid and r['appeared']]
        if not rows:raise ValueError('No observed outcomes; investigate coverage instead of filling zero')
        if any((r['game_id'],pid) not in starts for r in rows):raise ValueError('Missing start/relief evidence')
        outcomes.append({'case_id':case['case_id'],'player_id':case['player_id'],'season':case['season'],
                         'observed_appearances':len(rows),'observed_starts':sum(starts[r['game_id'],pid] for r in rows),
                         'observed_points':sum(r['points'] for r in rows),
                         'source_conflicts':sum(c['id']==pid for c in history['source_conflicts'])})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(dump_json({'outcomes':outcomes,'case_sha256':hashlib.sha256(a.cases.read_bytes()).hexdigest(),
        'history_sha256':hashlib.sha256(a.history.read_bytes()).hexdigest(),
        'goalie_box_sha256':hashlib.sha256(a.goalie_box.read_bytes()).hexdigest(),
        'warnings':['Retrospectively selected pilot cases, not a representative causal training sample',
                    'Outcome artifact must not be joined into pre-season predictor features',
                    'Full-season NHL fantasy points, not lineup value; source conflicts retained']}))
    print(dump_json(outcomes))


if __name__=='__main__':main()
