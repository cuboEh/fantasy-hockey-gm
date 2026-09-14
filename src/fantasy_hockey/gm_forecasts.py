"""Dated, provider-independent statistical rate estimates and forecast arithmetic."""

from collections import defaultdict
from datetime import date, timedelta

from .scoring import number, score

BASELINE = 'gm-rates-1'
CANDIDATE = 'gm-rates-recency-1'
MODELS = {BASELINE, CANDIDATE}


def estimate_rates(records, player_id, kind, cutoff, weights, model=BASELINE):
    """Use only earlier calendar dates; never interpret missing rows as absences.

    Twenty pooled appearance equivalents stabilize sparse histories. The candidate
    changes only individual recency weights, not the prior or evaluation cohort.
    """
    if model not in MODELS:
        raise ValueError('Unknown forecast model')
    if isinstance(cutoff, str):
        cutoff = date.fromisoformat(cutoff)
    lower = cutoff - timedelta(days=730)
    pool, own = [], []
    for row in records:
        day = date.fromisoformat(row['date'])
        if row['kind'] != kind or not lower <= day < cutoff or row.get('appeared') is not True:
            continue
        score(kind, row['stats'], weights)  # Missing scored stats fail, never become zero.
        pool.append(row)
        if row['id'] == player_id:
            own.append(row)
    required = sorted(k for k, v in weights.items() if number(v, k) != 0)
    if not own or not pool:
        return {'rates': None, 'history': None, 'reason': 'No observed appearance history before cutoff'}
    totals = {k: sum(float(r['stats'][k]) for r in own) for k in required}
    prior = {k: sum(float(r['stats'][k]) for r in pool) / len(pool) for k in required}
    factors = [1.0 if model == BASELINE else 2 ** (-(cutoff-date.fromisoformat(r['date'])).days/60)
               for r in own]
    effective = sum(factors)
    rates = {k: (sum(float(r['stats'][k])*w for r,w in zip(own,factors))+20*prior[k])/(effective+20)
             for k in required}
    return {'rates': rates, 'history': {'data_type': 'historical', 'appearances': len(own),
            'start': min(r['date'] for r in own), 'end': max(r['date'] for r in own),
            'totals': totals, 'points': float(score(kind, totals, weights).total)},
            'effective_appearances': effective, 'prior_appearances': 20, 'reason': None}


def forecast_points(row, weights, game_ids=None):
    """Expected stats precede scoring. Unknown workload returns no point total."""
    if row.get('rates') is None:
        return {'expected_appearances': None, 'stats': None, 'points': None,
                'reason': 'Projected scoring rates are missing'}
    games = [g for g in row.get('games', []) if game_ids is None or g['game_id'] in game_ids]
    if any(g['expected_appearances'] is None for g in games):
        return {'expected_appearances': None, 'stats': None, 'points': None,
                'reason': 'Participation is unknown for one or more games'}
    appearances = sum(g['expected_appearances'] for g in games)
    stats = {k: v*appearances for k,v in row['rates'].items()}
    return {'expected_appearances': appearances, 'stats': stats,
            'points': float(score(row['kind'], stats, weights).total), 'reason': None}


def validate_numeric_forecast(row, weights):
    """Validate the extended numerical contract, leaving legacy inventories readable."""
    from .gm_state import fields, text, timestamp
    required = {'kind', 'source', 'model_role', 'training_end', 'history', 'rates', 'games',
                'assumptions', 'missing_inputs'}
    if not required <= row.keys():
        raise ValueError('Numerical forecasts require rates, history, workload, provenance and assumptions')
    if row['kind'] not in ('skater', 'goalie') or row['model_role'] not in ('working', 'experimental'):
        raise ValueError('Invalid forecast kind or model role')
    if row['model_version']==CANDIDATE and row['model_role']!='experimental':
        raise ValueError('Recency candidate has not been promoted; it must remain experimental')
    text(row['source'], 'forecast source')
    issued = timestamp(row['issued_at'], 'issued_at')
    training_end = timestamp(row['training_end'], 'training_end')
    if training_end > issued:
        raise ValueError('Forecast training ends after issue time')
    if row['rates'] is not None:
        if not isinstance(row['rates'], dict):
            raise ValueError('Forecast rates must be a stat mapping')
        if any(type(v) not in (int,float) for v in row['rates'].values()):
            raise ValueError('Forecast rates must use finite JSON numbers')
        score(row['kind'], row['rates'], weights[row['kind']])
    history = row['history']
    if history is not None:
        fields(history, {'data_type', 'appearances', 'start', 'end', 'totals', 'points'}, 'forecast history')
        if history['data_type'] != 'historical' or type(history['appearances']) is not int or history['appearances'] < 1:
            raise ValueError('History must identify observed appearances')
        if not date.fromisoformat(history['start']) <= date.fromisoformat(history['end']) < training_end.date():
            raise ValueError('Historical observations must precede training cutoff date')
        actual = score(row['kind'], history['totals'], weights[row['kind']]).total
        if abs(actual-number(history['points'], 'historical points')) > number('0.000001','tolerance'):
            raise ValueError('Historical points do not reconcile with scoring weights')
    for key in ('assumptions', 'missing_inputs'):
        if not isinstance(row[key], list) or any(not isinstance(v,str) or not v.strip() for v in row[key]):
            raise ValueError(f'{key}: provide a list of explanations')
    if not isinstance(row['games'], list):
        raise ValueError('Forecast games must be a list')
    seen = set()
    for game in row['games']:
        fields(game, {'game_id', 'starts_at', 'expected_appearances', 'participation', 'basis'}, 'forecast game')
        text(game['game_id'], 'game ID'); text(game['basis'], 'participation basis')
        if game['game_id'] in seen:
            raise ValueError('Duplicate forecast game')
        seen.add(game['game_id'])
        start = timestamp(game['starts_at'], 'forecast game start')
        if not timestamp(row['horizon_start'],'horizon') <= start < timestamp(row['horizon_end'],'horizon'):
            raise ValueError('Forecast game outside horizon')
        status = game['participation']; value = game['expected_appearances']
        if status not in ('unknown', 'confirmed', 'projected', 'scenario'):
            raise ValueError('Invalid participation status')
        if value is None:
            if status != 'unknown':
                raise ValueError('Missing participation must be unknown')
        else:
            if type(value) not in (int,float):
                raise ValueError('Expected appearances must use a JSON number')
            value = number(value, 'expected appearances')
            if not 0 <= value <= 1 or status == 'unknown' or (status == 'confirmed' and value not in (0,1)):
                raise ValueError('Invalid appearance expectation or confirmation')


class RateHistory:
    """Chronological sufficient statistics, equivalent to estimate_rates."""

    def __init__(self, weights):
        from collections import deque
        self.weights = weights
        self.rows = deque()
        self.own = defaultdict(deque)
        self.pool = defaultdict(lambda: defaultdict(float))
        self.counts = defaultdict(int)
        self.cutoff = None

    def advance(self, cutoff):
        if self.cutoff and cutoff < self.cutoff:
            raise ValueError('History cutoff cannot move backwards')
        self.cutoff = cutoff
        lower = cutoff - timedelta(days=730)
        while self.rows and date.fromisoformat(self.rows[0]['date']) < lower:
            row = self.rows.popleft(); self.own[row['id']].popleft()
            self.counts[row['kind']] -= 1
            for k,v in row['stats'].items():
                self.pool[row['kind']][k] -= float(v)

    def add(self, row):
        if row.get('appeared') is not True:
            return
        if self.rows and row['date'] < self.rows[-1]['date']:
            raise ValueError('History rows must be chronological')
        score(row['kind'], row['stats'], self.weights[row['kind']])
        self.rows.append(row); self.own[row['id']].append(row)
        self.counts[row['kind']] += 1
        for k,v in row['stats'].items():
            self.pool[row['kind']][k] += float(v)

    def rates(self, player_id, kind, model=BASELINE):
        if model not in MODELS or self.cutoff is None:
            raise ValueError('A known model and cutoff are required')
        own = self.own[player_id]
        if not own:
            return None
        if any(date.fromisoformat(r['date']) >= self.cutoff for r in own):
            raise ValueError('Future or same-day history cannot enter a forecast')
        if self.rows and date.fromisoformat(self.rows[-1]['date']) >= self.cutoff:
            raise ValueError('Future pooled history cannot enter a forecast')
        factors = [1 if model == BASELINE else 2**(-(self.cutoff-date.fromisoformat(r['date'])).days/60)
                   for r in own]
        return {k: (sum(float(r['stats'][k])*w for r,w in zip(own,factors))+
                    20*self.pool[kind][k]/self.counts[kind])/(sum(factors)+20)
                for k,v in self.weights[kind].items() if v != 0}


def build_forecasts(histories, snapshot, *, issued_at, horizon_end, source, model=BASELINE,
                    participation=None):
    """Build rates from supplied histories; workload requires separately dated evidence.

    Local normalized player IDs may use the existing nhl: prefix. Unknown identities
    stay unsupported; names are never used to guess a join.
    """
    from copy import deepcopy
    from datetime import datetime, time, timezone
    from .gm_state import timestamp, validate_snapshot
    issued=timestamp(issued_at,'issue');end=timestamp(horizon_end,'horizon end')
    if end<=issued:raise ValueError('Forecast horizon must follow issue time')
    payload=deepcopy(snapshot);inputs=payload['inputs']
    config=(inputs['settings']['data'] or {}).get('config')
    if config is None:raise ValueError('Scoring configuration required')
    weights=config['scoring'];engine=RateHistory(weights)
    conflicts={(c['game_id'],c['id']) for h in histories for c in h.get('source_conflicts',[])}
    rows=sorted((r for h in histories for r in h['records']
                 if date.fromisoformat(r['date'])<issued.date()
                 and date.fromisoformat(r['date'])>=issued.date()-timedelta(days=730)
                 and (r['game_id'],r['id']) not in conflicts),key=lambda r:r['date'])
    seen=set()
    for row in rows:
        key=(row['game_id'],row['id'])
        if key in seen:raise ValueError('Duplicate source history player-game')
        seen.add(key);engine.add(row)
    engine.advance(issued.date())
    players={r['id']:r for r in (inputs.get('players') or {}).get('data') or []}
    players.update({r['id']:r for r in inputs['roster']['data'] or []})
    schedule=inputs['schedule']['data'] or [];forecasts=[]
    participation=participation or {}
    for player in players.values():
        identity=player['id'].removeprefix('nhl:')
        own=engine.own[identity]
        if player['positions']==['G']:
            kind='goalie'
        elif player['positions']:
            kind='skater'
        elif own:
            kind=own[-1]['kind']  # Historical stat kind does not establish current eligibility.
        else:
            continue  # Unsupported identity remains in the searchable player inventory.
        rates=engine.rates(identity,kind,model)
        keys=sorted(k for k,v in weights[kind].items() if number(v,k)!=0)
        history=None
        if own:
            totals={k:sum(float(r['stats'][k]) for r in own) for k in keys}
            history={'data_type':'historical','appearances':len(own),'start':own[0]['date'],
                'end':own[-1]['date'],'totals':totals,'points':float(score(kind,totals,weights[kind]).total)}
        games=[];missing=[]
        for game in schedule:
            if player['nhl_team'] not in game['teams'] or not issued<=timestamp(game['starts_at'],'start')<end:continue
            expectation=participation.get(player['id'],{}).get(game['id'])
            if expectation is None:
                expectation={'expected_appearances':None,'participation':'unknown','basis':'No dated workload evidence supplied'}
                missing.append('Participation for '+game['id'])
            else:
                if timestamp(expectation['observed_at'],'participation observation')>issued:
                    raise ValueError('Future participation evidence cannot enter forecast')
                if 'eligible_history' in expectation:
                    expectation=estimate_participation(expectation['eligible_history'],issued.date(),model)
                else:
                    expectation={k:expectation[k] for k in ('expected_appearances','participation','basis')}
            games.append({'game_id':game['id'],'starts_at':game['starts_at'],**expectation})
        if rates is None:missing.append('No observed appearance history before issue date')
        if inputs['schedule']['coverage']=='missing':missing.append('Schedule not supplied')
        forecasts.append({'id':player['id'],'kind':kind,'data_type':'projection','model_version':model,
            'model_role':'working' if model==BASELINE else 'experimental','source':source,'issued_at':issued.isoformat(),
            'training_end':datetime.combine(issued.date(),time(),timezone.utc).isoformat(),
            'horizon_start':issued.isoformat(),'horizon_end':end.isoformat(),'history':history,'rates':rates,'games':games,
            'assumptions':['Previous 730 days; 20 same-kind pooled appearance equivalents',
                'Rates conditional on appearance; no missing-game zero fill',
                'No injury, deployment or opponent adjustment',
                'Reconstructed historical statistics; source publication lag not established'],
            'missing_inputs':missing})
    inputs['forecasts']={'source':source,'observed_at':issued.isoformat(),'expires_at':None,
        'coverage':'complete','reason':None,'data':forecasts}
    return validate_snapshot(payload,payload['league']['id'],payload['team']['id'],issued)


def estimate_participation(observations, cutoff, model=BASELINE):
    """Beta-smoothed appearances conditional on an explicitly supplied eligible cohort.

    Callers must establish roster membership independently. Missing dates are never
    added to the denominator. This is an uncalibrated baseline, not confirmation.
    """
    if model not in MODELS:raise ValueError('Unknown workload model')
    if isinstance(cutoff,str):cutoff=date.fromisoformat(cutoff)
    rows=[r for r in observations if cutoff-timedelta(days=730)<=date.fromisoformat(r['date'])<cutoff
          and type(r.get('appeared')) is bool]
    if not rows:return {'expected_appearances':None,'participation':'unknown','basis':'No explicit eligible-cohort observations'}
    factors=[1 if model==BASELINE else 2**(-(cutoff-date.fromisoformat(r['date'])).days/60) for r in rows]
    return {'expected_appearances':(1+sum(int(r['appeared'])*w for r,w in zip(rows,factors)))/(2+sum(factors)),
            'participation':'projected','basis':f'Beta(1,1) eligible-cohort baseline; {len(rows)} explicit observations; calibration unverified'}
