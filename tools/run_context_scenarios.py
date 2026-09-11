"""Evaluate a private contextual-scenario dossier without changing the live draft."""
import argparse
from datetime import date
import hashlib
from pathlib import Path
from fantasy_hockey.board import read_json,dump_json
from fantasy_hockey.context_scenarios import evaluate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.md').exists():p.error('Use a new output path')
    result=evaluate(read_json(a.board),read_json(a.input),a.as_of)
    result['input_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest()
    result['board_sha256']=hashlib.sha256(a.board.read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(dump_json(result))
    lines=['# Contextual draft scenarios','',*result['warnings'],'',
           '| Player | Conditional case | Appearances | FP | Baseline change |','| --- | --- | ---: | ---: | ---: |']
    for r in result['results']:
        lines.append(f"| {r['player']} | {r['case']} | {r['appearances']:.1f} | {r['points']:.1f} | {r['delta_from_baseline']:+.1f} |")
    cited={}
    for r in result['results']:
        lines+=['',f"## {r['player']}: {r['case']}",'','Analyst assumptions: '+r['assumptions'],
                '', 'Before relying on this case: '+r['confirmation_needed'],'','Review by: '+r['review_by']]
        if 'workload_only_delta' in r:
            lines += ['',f"Delta attribution: workload at old per-appearance rate {r['workload_only_delta']:+.1f} FP; switching to conditional start/relief rates {r['conditional_rate_delta']:+.1f} FP."]
        for e in r['evidence']:
            cited[e['source']]=e
    lines+=['','## Evidence']
    for e in cited.values():lines+=['',f"{e['date']}: {e['fact']} [Source]({e['source']})"]
    a.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(a.output.with_suffix('.md'))


if __name__=='__main__':main()
