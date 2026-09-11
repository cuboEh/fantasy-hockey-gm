"""Compare prior-only goalie rate estimates with next-season conditional start outcomes."""
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from statistics import mean
from fantasy_hockey.goalie_rates import estimate_rates
from fantasy_hockey.seasonlab import prepare_history
from fantasy_hockey.backtest import Model,forecast
from fantasy_hockey.config import load_config


def main():
    output=Path('var/starter-rate-validation-2026-09-10.json')
    if output.exists():raise ValueError('Preserve the existing validation artifact')
    weights=load_config(Path('config.local.toml')).weights['goalie'];cache={};records=[];inputs={}
    def load(year):
        if year not in cache:
            h=Path(f'var/history-{year}.json');b=Path(f'snapshots/2026-09-10/sportsdataverse/goalie_box_{year}.csv')
            history=json.loads(h.read_text())
            with b.open() as f:boxes=list(csv.DictReader(f))
            cache[year]=(history,estimate_rates(history,boxes,weights,date(year,9,13)))
            inputs[str(h)]=hashlib.sha256(h.read_bytes()).hexdigest();inputs[str(b)]=hashlib.sha256(b.read_bytes()).hexdigest()
        return cache[year]
    for year in range(2015,2027):
        prior=load(year-1)[1];actual=load(year)[1]
        histories={y:load(y)[0] for y in range(max(2013,year-3),year)}
        _,history=prepare_history(histories,year);base={p.id:p for p in forecast(history,Model())}
        for pid,p in prior['players'].items():
            observed=actual['players'].get(pid,{}).get('start',{})
            if not p['start']['sample'] or observed.get('sample',0)<20 or pid.removeprefix('nhl:') not in base:continue
            rate=observed['mean_points']
            records.append({'year':year,'id':pid,'actual_start_sample':observed['sample'],
                            'baseline_appearance_error':abs(base[pid.removeprefix('nhl:')].rate-rate),
                            'raw_start_error':abs(p['start']['mean_points']-rate),
                            'shrunk_start_error':abs(p['start']['shrunk_points']-rate)})
    metrics=('baseline_appearance_error','raw_start_error','shrunk_start_error')
    result={'cases':len(records),'mae':{m:mean(r[m] for r in records) for m in metrics},
            'years':{y:{m:mean(r[m] for r in records if r['year']==y) for m in metrics} for y in range(2015,2027)},
            'rows':records,'input_sha256':inputs,
            'warnings':['Previously explored seasons; not an untouched holdout',
                        'Conditional rate check limited to returners with at least 20 clean target starts; does not test injury/workload prediction',
                        'Prior strength fixed at 20 before comparison; no grid search or selection on these outcomes']}
    with output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in {'rows','input_sha256'}},indent=2))


if __name__=='__main__':main()
