from datetime import date, datetime, timezone
import unittest
from copy import deepcopy

from fantasy_hockey.gm_forecasts import BASELINE, CANDIDATE, RateHistory, estimate_rates, forecast_points
from research.evaluate_gm_rates import evaluate

WEIGHTS={'skater':{'goals':6,'shots_on_goal':1},'goalie':{'wins':5,'goals_against':-3}}


def row(i, player='p', goals=1):
    return {'id':player,'game_id':str(i),'date':f'2026-01-{i:02d}',
            'kind':'skater','appeared':True,'stats':{'goals':goals,'shots_on_goal':3}}


class ForecastTests(unittest.TestCase):
    def test_streaming_matches_reference_and_excludes_same_day_and_future(self):
        records=[row(i) for i in range(1,20)]+[row(20,goals=999)]
        model=RateHistory(WEIGHTS)
        for r in records[:-1]:model.add(r)
        model.advance(date(2026,1,20))
        for version in (BASELINE,CANDIDATE):
            actual=model.rates('p','skater',version)
            expected=estimate_rates(records,'p','skater','2026-01-20',WEIGHTS['skater'],version)
            for k in actual:self.assertAlmostEqual(actual[k],expected['rates'][k])
        model.add(records[-1])
        with self.assertRaisesRegex(ValueError,'same-day'):model.rates('p','skater')

    def test_missing_history_and_workload_are_not_zero(self):
        self.assertIsNone(estimate_rates([], 'p','skater','2026-01-20',WEIGHTS['skater'])['rates'])
        forecast={'kind':'skater','rates':{'goals':1,'shots_on_goal':3},
                  'games':[{'game_id':'a','expected_appearances':None}]}
        self.assertIsNone(forecast_points(forecast,WEIGHTS['skater'])['points'])
        forecast['games'][0]['expected_appearances']=0.5
        self.assertEqual(forecast_points(forecast,WEIGHTS['skater'])['points'],4.5)
        self.assertEqual(forecast_points(forecast,WEIGHTS['skater'],set())['points'],0)

    def test_chronological_cases_and_conflicts_are_excluded(self):
        history={'records':[row(i) for i in range(1,25)],
                 'source_conflicts':[{'id':'p','game_id':'11'}]}
        before=deepcopy(history)
        result=evaluate([history],WEIGHTS,'2026-01-11','2026-01-24')
        self.assertEqual(len(result['ledger']),13)
        self.assertEqual(result['ledger'][0]['history_appearances'],10)
        self.assertEqual(result['ledger'][0]['game_id'],'12')
        self.assertEqual(result['ledger'][0]['baseline_points'],9)
        self.assertEqual(history,before)
        self.assertFalse(result['promoted'])

    def test_explicit_nonappearance_does_not_train_rate(self):
        records=[row(1),row(2,goals=0)];records[1]['appeared']=False
        prediction=estimate_rates(records,'p','skater','2026-01-03',WEIGHTS['skater'])
        self.assertEqual(prediction['history']['appearances'],1)
        self.assertEqual(prediction['rates']['goals'],1)

    def test_build_validated_rates_rejects_future_workload_and_unpromoted_candidate(self):
        from fantasy_hockey.gm_forecasts import build_forecasts
        from fantasy_hockey.gm_state import validate_snapshot
        from test_gm_advice import decision_snapshot
        from test_gm import NOW
        p=decision_snapshot()
        records=[{**row(i,player='center'),'date':f'2026-01-{i:02d}'} for i in range(1,20)]
        result=build_forecasts([{'records':records}],p,issued_at=NOW.isoformat(),
            horizon_end='2026-09-20T00:00:00Z',source='fictional history')
        f=next(r for r in result['inputs']['forecasts']['data'] if r['id']=='center')
        self.assertIsNotNone(f['rates']);self.assertIsNone(f['games'][0]['expected_appearances'])
        p=deepcopy(result);f=p['inputs']['forecasts']['data'][0]
        f['model_version']=CANDIDATE;f['model_role']='working'
        with self.assertRaisesRegex(ValueError,'not been promoted'):
            validate_snapshot(p,'demo-league','demo-team',NOW)
        with self.assertRaisesRegex(ValueError,'Future participation'):
            build_forecasts([{'records':records}],result,issued_at=NOW.isoformat(),
                horizon_end='2026-09-20T00:00:00Z',source='fixture',
                participation={'center':{'game0':{'observed_at':'2026-09-20T00:00:00Z'}}})

    def test_workload_estimation_requires_explicit_cohort(self):
        from fantasy_hockey.gm_forecasts import estimate_participation
        self.assertIsNone(estimate_participation([],'2026-02-01')['expected_appearances'])
        rows=[{'date':'2026-01-01','appeared':True},{'date':'2026-01-02','appeared':False},
              {'date':'2026-01-03','appeared':None},{'date':'2026-02-01','appeared':True}]
        self.assertEqual(estimate_participation(rows,'2026-02-01')['expected_appearances'],0.5)

    def test_frozen_forecast_outcomes_and_backdating_exclusion(self):
        from fantasy_hockey.gm_evaluation import evaluate_frozen
        from test_gm_advice import decision_snapshot
        from test_gm import NOW
        from datetime import timedelta
        p=decision_snapshot();game=p['inputs']['schedule']['data'][0]
        outcomes=[{'player_id':'center','game_id':'game0','starts_at':game['starts_at'],
            'observed_at':(NOW+timedelta(hours=5)).isoformat(),'appeared':True,
            'stats':{'goals':1,'shots_on_goal':0}}]
        review={'at':NOW.isoformat(),'snapshot':p}
        report=evaluate_frozen([review,review],outcomes,NOW+timedelta(hours=6))
        self.assertEqual(report['metrics']['fixture-1:skater']['n'],1)
        self.assertEqual(report['metrics']['fixture-1:skater']['point_mae'],3)
        review['at']=(NOW+timedelta(hours=6)).isoformat()
        self.assertEqual(evaluate_frozen([review],outcomes,NOW+timedelta(hours=6))['metrics'],{})
