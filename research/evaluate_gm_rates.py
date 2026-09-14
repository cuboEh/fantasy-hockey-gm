"""One predeclared chronological comparison; reconstructed history is development evidence."""

import argparse
from collections import defaultdict
from datetime import date
import hashlib
from itertools import groupby
import json
from pathlib import Path
import random

from fantasy_hockey.config import load_config
from fantasy_hockey.gm_forecasts import BASELINE, CANDIDATE, RateHistory
from fantasy_hockey.scoring import score


def paired_interval(blocks, seed=20260914):
    if len(blocks) < 2:
        return None
    rng = random.Random(seed); values=[]; blocks=list(blocks.values())
    for _ in range(200):
        sample = rng.choices(blocks, k=len(blocks))
        values.append(sum(s for s,n in sample)/sum(n for s,n in sample))
    values.sort()
    return [values[4], values[194]]


def evaluate(histories, weights, start, end):
    conflicts={(c['game_id'],c['id']) for h in histories for c in h.get('source_conflicts',[])}
    rows=sorted((r for h in histories for r in h['records']), key=lambda r:(r['date'],r['game_id'],r['id']))
    identities=[(r['game_id'],r['id']) for r in rows]
    if len(set(identities))!=len(identities):
        raise ValueError('Duplicate evaluation player-game')
    model=RateHistory(weights); metrics={}; coverage=defaultdict(int); ledger=[]
    workload=defaultdict(list)
    for day, group in groupby(rows,key=lambda r:r['date']):
        cutoff=date.fromisoformat(day); model.advance(cutoff); today=list(group)
        for row in today:
            key=(row['game_id'],row['id'])
            if key in conflicts:
                if start <= day <= end: coverage['source_conflicts_excluded']+=1
                continue
            if not start <= day <= end: continue
            kind=row['kind']; observed=row.get('appeared')
            if observed not in (True,False):
                coverage[kind+'_participation_unknown']+=1; continue
            if kind=='goalie':
                prior=[r for r in workload[row['id']] if (cutoff-date.fromisoformat(r['date'])).days<=730]
                if len(prior)>=10:
                    factors=[2**(-(cutoff-date.fromisoformat(r['date'])).days/60) for r in prior]
                    probabilities=[(1+sum(r['appeared'] for r in prior))/(2+len(prior)),
                                   (1+sum(r['appeared']*w for r,w in zip(prior,factors)))/(2+sum(factors))]
                    bucket=metrics.setdefault('goalie_listed_workload', {'n':0,'baseline_brier':0,'candidate_brier':0,
                        'baseline_mae':0,'candidate_mae':0,'blocks':defaultdict(lambda:[0,0])})
                    errors=[(p-int(observed))**2 for p in probabilities];bucket['n']+=1
                    for label,p,error in zip(('baseline','candidate'),probabilities,errors):
                        bucket[label+'_brier']+=error;bucket[label+'_mae']+=abs(p-int(observed))
                    block=bucket['blocks'][cutoff.strftime('%G-%V')];block[0]+=errors[1]-errors[0];block[1]+=1
            if observed is not True:
                coverage[kind+'_explicit_nonappearance']+=1;continue
            n=len(model.own[row['id']]);coverage[kind+'_observed']+=1
            if n<10:
                coverage[kind+'_sparse_excluded']+=1;continue
            rates=[model.rates(row['id'],kind,m) for m in (BASELINE,CANDIDATE)]
            actual=float(score(kind,row['stats'],weights[kind]).total)
            predictions=[float(score(kind,r,weights[kind]).total) for r in rates]
            ledger.append({'id':row['id'],'game_id':row['game_id'],'date':day,'kind':kind,
                'history_appearances':n,'baseline_rates':rates[0],'candidate_rates':rates[1],
                'actual_stats':row['stats'],'actual_points':actual,'baseline_points':predictions[0],
                'candidate_points':predictions[1]})
            for group_name in (kind,kind+('_10_29' if n<30 else '_30_plus')):
                bucket=metrics.setdefault(group_name,{'n':0,'baseline_mae':0,'candidate_mae':0,
                    'baseline_bias':0,'candidate_bias':0,'stats':{},'blocks':defaultdict(lambda:[0,0])})
                bucket['n']+=1;errors=[p-actual for p in predictions]
                for label,error,r in zip(('baseline','candidate'),errors,rates):
                    bucket[label+'_mae']+=abs(error);bucket[label+'_bias']+=error
                    for stat,v in r.items():
                        bucket['stats'].setdefault(stat,{'baseline_mae':0,'candidate_mae':0})[label+'_mae']+=abs(v-float(row['stats'][stat]))
                block=bucket['blocks'][cutoff.strftime('%G-%V')];block[0]+=abs(errors[1])-abs(errors[0]);block[1]+=1
        # Outcomes enter only after every forecast on this date has been made.
        for row in today:
            if (row['game_id'],row['id']) in conflicts: continue
            model.add(row)
            if row['kind']=='goalie' and type(row.get('appeared')) is bool:
                workload[row['id']].append(row)
    for bucket in metrics.values():
        bucket['paired_week_interval']=paired_interval(bucket.pop('blocks'))
        for key in list(bucket):
            if key.endswith(('_mae','_bias','_brier')):bucket[key]/=bucket['n']
        for stat in bucket.get('stats',{}).values():
            for key in stat:stat[key]/=bucket['n']
    return {'coverage':dict(coverage),'metrics':metrics,'ledger':ledger,'promoted':False,
            'interpretation':'Development comparison; conditional observed-game rates and listed-goalie workload only'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history',type=Path,nargs='+',required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise ValueError('Preserve evidence: output already exists')
    plan=json.loads(args.plan.read_text())
    raw_inputs={path:path.read_bytes() for path in [*args.history,args.config,args.plan]}
    histories=[json.loads(raw_inputs[path]) for path in args.history]
    if sorted(h['ending_year'] for h in histories)!=[2024,2025,2026]:raise ValueError('Declared input seasons are 2024-2026')
    result=evaluate(histories,load_config(args.config).weights,'2025-10-01','2026-04-30')
    result['plan']=plan
    result['input_sha256']={str(path):hashlib.sha256(raw).hexdigest() for path,raw in raw_inputs.items()}
    args.output.mkdir(parents=True)
    ledger=result.pop('ledger')
    with (args.output/'predictions.jsonl').open('x') as f:
        for row in ledger:f.write(json.dumps(row)+'\n')
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'cases':len(ledger),'metrics':result['metrics'],'output':str(args.output)}))


if __name__=='__main__':main()
