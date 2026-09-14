"""Evaluate frozen GM forecast inputs against separately observed outcomes."""

from collections import defaultdict
from .gm_forecasts import forecast_points
from .gm_state import timestamp
from .scoring import score


def evaluate_frozen(reviews, outcomes, now):
    """Earliest saved pre-game review per model/player/game; no repeated-review weighting."""
    actual={}
    for row in outcomes:
        key=(row['player_id'],row['game_id'])
        if key in actual:raise ValueError('Duplicate outcome player-game')
        if type(row['appeared']) is not bool:raise ValueError('Outcome participation must be explicit')
        if not timestamp(row['starts_at'],'start')<timestamp(row['observed_at'],'observed')<=now:
            raise ValueError('Outcome timestamps do not establish a completed observation')
        actual[key]=row
    counts=defaultdict(int);metrics={};seen=set()
    for review in sorted(reviews,key=lambda r:r['at']):
        saved=timestamp(review['at'],'saved review');snapshot=review['snapshot']
        weights=snapshot['inputs']['settings']['data']['config']['scoring']
        for f in snapshot['inputs']['forecasts']['data'] or []:
            if 'rates' not in f:continue
            for game in f['games']:
                key=(f['id'],game['game_id']);identity=(f['model_version'],*key)
                if identity in seen:continue
                start=timestamp(game['starts_at'],'start')
                if saved>=start:
                    counts['not_frozen_before_game']+=1;continue
                row=actual.get(key)
                if row is None:counts['outcome_missing']+=1;continue
                if timestamp(row['starts_at'],'actual start')!=start:
                    raise ValueError('Outcome game time differs from frozen forecast')
                if timestamp(f['issued_at'],'issue')>saved:raise ValueError('Forecast issued after saved review')
                observed=score(f['kind'],row['stats'],weights[f['kind']])
                if not row['appeared'] and any(float(v)!=0 for v in row['stats'].values()):
                    raise ValueError('Nonappearance outcome contains nonzero statistics')
                expected=forecast_points(f,weights[f['kind']],{game['game_id']})
                if expected['points'] is None:
                    counts['unsupported_forecast']+=1;continue
                if game['participation']=='scenario':
                    counts['conditional_scenario_excluded']+=1;continue
                seen.add(identity)
                group=f['model_version']+':'+f['kind']
                b=metrics.setdefault(group,{'n':0,'point_mae':0,'appearance_mae':0,'participation_brier':0,
                                            'appeared_n':0,'rate_point_mae':0,'stat_mae':defaultdict(float)})
                b['n']+=1
                delta=expected['expected_appearances']-int(row['appeared'])
                b['point_mae']+=abs(expected['points']-float(observed.total))
                b['appearance_mae']+=abs(delta);b['participation_brier']+=delta*delta
                if row['appeared']:
                    b['appeared_n']+=1
                    b['rate_point_mae']+=abs(float(score(f['kind'],f['rates'],weights[f['kind']]).total)-float(observed.total))
                    for stat,v in f['rates'].items():b['stat_mae'][stat]+=abs(v-float(row['stats'][stat]))
    for b in metrics.values():
        for k in ('point_mae','appearance_mae','participation_brier'):b[k]/=b['n']
        if b['appeared_n']:
            b['rate_point_mae']/=b['appeared_n']
            b['stat_mae']={k:v/b['appeared_n'] for k,v in b['stat_mae'].items()}
        else:b['rate_point_mae']=None;b['stat_mae']={}
    return {'metrics':metrics,'coverage':dict(counts),'promoted':False,
        'baseline':'gm-rates-1; separate beta-smoothed cohort workload when available',
        'limitation':'This report measures frozen versions. Differing coverage is not a paired promotion comparison.'}
