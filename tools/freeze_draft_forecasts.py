"""Freeze projections before outcomes exist, for prospective retrospective evaluation."""
import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from fantasy_hockey.decision_cli import build_players


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('board','workloads','rates','context','case-map','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True);a=p.parse_args()
    if a.output.exists():p.error('Forecast snapshot exists; use a new version')
    paths={k:getattr(a,k) for k in ('board','workloads','rates','context','case_map')}
    inputs={k:json.loads(p.read_text()) for k,p in paths.items()}
    players,notes=build_players(inputs['board'],inputs['workloads'],inputs['rates'],a.as_of,inputs['context'],inputs['case_map'])
    payload={'model':'two_turn_scenario_v1','season':inputs['board']['season'],'as_of':a.as_of.isoformat(),
             'generated_at':datetime.now(timezone.utc).isoformat(),'players':[asdict(p) for p in players],'notes':notes,
             'input_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},
             'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/fantasy_hockey').glob('*.py')},
             'evaluation_plan':['Do not tune this snapshot against its target season; preserve later revisions separately',
                                'Measure games/starts error, conditional scoring-rate error and season points error separately',
                                'Absent players count as zero season production, not missing cases; conditional-rate error only where appearances exist',
                                'Compare usable roster points and missed minimums using actual recorded draft decisions and league periods',
                                'Report source conflicts, unavailable outcomes and coverage explicitly; do not silently drop failures',
                                'Analyst downside cases have no assigned probabilities, so do not score them as confidence intervals'],
             'promotion':'experimental; not automatically selected for live picks'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(payload,f,indent=2)
    print(a.output)


if __name__=='__main__':main()
