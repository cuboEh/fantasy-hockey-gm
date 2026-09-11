"""Prioritize contextual review with explicit workload sensitivities, not forecasts."""
import argparse
from datetime import date
import hashlib
from pathlib import Path
from fantasy_hockey.board import read_json, dump_json
from fantasy_hockey.scoring import number


def build_review(board, evidence, as_of):
    if date.fromisoformat(board['as_of']) > as_of:
        raise ValueError('Board is after analysis date')
    players={p['id']:p for p in board['players']}
    rows=[];seen=set()
    for item in evidence['players']:
        pid=item['id']
        if pid in seen or pid not in players:raise ValueError('Duplicate or unknown review ID')
        seen.add(pid)
        if not item.get('fact') or not item.get('source') or not item.get('questions'):
            raise ValueError('Review needs sourced fact and unresolved questions')
        if date.fromisoformat(item['evidence_date']) > as_of:
            raise ValueError('Evidence is after analysis date')
        p=players[pid]
        if p['projected_points'] is None:
            scenarios=[]
        else:
            gp=number(p['projected_games'],'appearances');rate=number(p['points_per_game'],'rate')
            cap=number(board['assumptions']['season_games'],'season games')
            scenarios=[{'case':name,'appearances':games,'points':games*rate,'delta':(games-gp)*rate}
                       for name,games in [('lower workload',max(0,gp-10)),('historical workload',gp),('higher workload',min(cap,gp+10))]]
        rows.append({'id':pid,'name':p['name'],'team':p['team'],'kind':p['kind'],
                     'evidence':item,'baseline_points':p['projected_points'],'workload_sensitivity':scenarios})
    return {'as_of':as_of.isoformat(),'rows':rows,
            'warnings':['Workload cases are baseline +/-10 appearances, bounded by season length, not predicted recovery dates or start allocations',
                        'Per-appearance scoring held fixed; no assumed rate benefit from better teammates',
                        'No probabilities or most-likely case assigned; historical workload is not a reviewed base forecast',
                        'Goalie appearances are not starts; shared team starts require a joint allocation before promoting a forecast',
                        'Research report only; live draft board is unchanged']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.md').exists():p.error('Use a new output path')
    result=build_review(read_json(a.board),read_json(a.evidence),a.as_of)
    result['board_sha256']=hashlib.sha256(a.board.read_bytes()).hexdigest()
    result['evidence_sha256']=hashlib.sha256(a.evidence.read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(dump_json(result))
    lines=['# Contextual workload review','',*result['warnings'],'']
    for row in result['rows']:
        e=row['evidence']
        lines += ['## '+row['name'],'',f"Fact ({e['evidence_date']}): {e['fact']} [Source]({e['source']})",'',
                  'To resolve: '+'; '.join(e['questions']), '',
                  '| Sensitivity case | Appearances | Fantasy points | Change |','| --- | ---: | ---: | ---: |']
        for scenario in row['workload_sensitivity']:
            lines.append(f"| {scenario['case']} | {scenario['appearances']:.1f} | {scenario['points']:.1f} | {scenario['delta']:+.1f} |")
        lines.append('')
    a.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(a.output.with_suffix('.md'))


if __name__=='__main__':main()
