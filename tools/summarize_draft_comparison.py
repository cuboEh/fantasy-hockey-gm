"""Paired diagnostics with season-cluster resampling, not a forecast of league wins."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
from statistics import mean


def summarize(directories, reference='coverage_frozen'):
    groups=defaultdict(dict)
    hashes={}
    for directory in directories:
        if not (directory/'summary.json').exists():
            raise ValueError('Draft study is not complete: '+str(directory))
        path=directory/'rows.json'
        manifest=json.loads((directory/'manifest.json').read_text())
        hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        for row in json.loads(path.read_text()):
            key=(row['year'],row['style'],row['seat'],manifest['seed'])
            if row['policy'] in groups[key]:
                raise ValueError('Duplicate paired scenario')
            groups[key][row['policy']]=row
    if not groups or any(reference not in rows for rows in groups.values()):
        raise ValueError('Every scenario needs the reference policy')
    policies=set.intersection(*(set(rows) for rows in groups.values()))-{reference}
    results={}
    for policy in sorted(policies):
        pairs=[]
        for key,rows in sorted(groups.items()):
            a,b=rows[policy],rows[reference]
            if a['common_clean_weeks']!=b['common_clean_weeks']:
                raise ValueError('Mismatched replay-week exposure')
            pairs.append({'year':key[0],'style':key[1],'seat':key[2],'seed':key[3],
                          'points_delta':a['common_clean_points']-b['common_clean_points'],
                          'missed_weeks_delta':a['common_clean_failed_weeks']-b['common_clean_failed_weeks']})
        years=sorted({r['year'] for r in pairs})
        annual={year:mean(r['points_delta'] for r in pairs if r['year']==year) for year in years}
        rng=random.Random(914)
        samples=sorted(mean(annual[rng.choice(years)] for _ in years) for _ in range(5000))
        results[policy]={'paired_scenarios':len(pairs),'seasons':len(years),
                         'mean_points_delta':mean(r['points_delta'] for r in pairs),
                         'mean_missed_weeks_delta':mean(r['missed_weeks_delta'] for r in pairs),
                         'positive_scenarios':sum(r['points_delta']>0 for r in pairs),
                         'positive_season_means':sum(v>0 for v in annual.values()),
                         'season_balanced_points_delta':mean(annual.values()),
                         'season_bootstrap_95_interval':[samples[125],samples[4874]],'pairs':pairs}
    return {'reference':reference,'comparisons':results,'input_sha256':hashes,
            'warning':'Previously explored historical seasons and synthetic markets. Descriptive season-cluster bootstrap, not a future win probability. Missing policies are omitted from the common comparison.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directories',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=summarize(a.directories)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:{n:v for n,v in r.items() if n!='pairs'} for k,r in result['comparisons'].items()},indent=2))


if __name__=='__main__':main()
