from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from fantasy_hockey.backtest import (Forecast, Model, historical_input, forecast,
    mock_draft, evaluate_picks, replacement_levels, run_study)
from fantasy_hockey.config import load_config
from test_board import dataset


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.config=load_config(Path(__file__).resolve().parents[1]/'config.example.toml')

    def test_future_results_and_current_rank_do_not_change_forecast(self):
        data=dataset()
        before=forecast(historical_input(data,self.config,2025),Model())
        modified=deepcopy(data)
        modified['players'][0]['seasons'][0]['cats']['G']=10000
        modified['players'][0]['consensus']={'avg':1}
        modified['players'][0]['team']='NEW'
        after=forecast(historical_input(modified,self.config,2025),Model())
        self.assertEqual(before,after)

    def test_fixed_two_season_recency_weights(self):
        history=[('1','Example','C','skater',[(2023,80,800),(2024,80,1600)])]
        prediction=forecast(history,Model())[0]
        self.assertAlmostEqual(prediction.rate,17.5)
        self.assertEqual(prediction.games,80)

    def test_future_only_player_excluded(self):
        data=dataset()
        history=historical_input(data,self.config,2025)
        self.assertEqual([p[0] for p in history],['1'])

    def test_missing_result_is_not_zero(self):
        picks=[{'id':'1','team':1},{'id':'2','team':1}]
        result=evaluate_picks(picks,{'1':{'points':100}},1)
        self.assertIsNone(result['complete_points'])
        self.assertEqual(result['missing_outcome_ids'],['2'])
        self.assertEqual(result['known_points'],100)

    def test_draft_reproducibility_snake_and_capacity(self):
        pool=[Forecast(str(i),str(i),'C' if i%2 else 'G','skater' if i%2 else 'goalie',10,10,100-i) for i in range(12)]
        args=(pool,pool,{'C':1,'G':1,'BN':1},2,1,42,'replacement')
        picks=mock_draft(*args)
        self.assertEqual(picks,mock_draft(*args))
        self.assertEqual([p['team'] for p in picks],[1,2,2,1,1,2])
        self.assertEqual(len({p['id'] for p in picks}),6)
        self.assertEqual(sum(p['team']==1 for p in picks),3)
        self.assertEqual(replacement_levels(pool,{'C':1,'G':1},2)['C'],95)

    def test_evaluation_only_receives_locked_winner(self):
        calls=[]
        def fake(data,config,target,model,scenarios):
            calls.append((target,model))
            return {'runs':[{'paired_delta':float(model.shrink_games)} for _ in scenarios]}
        with patch('fantasy_hockey.backtest.experiment',side_effect=fake):
            report=run_study({},self.config)
        self.assertEqual([target for target,_ in calls],[2024]*8+[2025])
        self.assertEqual(report['selected_model']['shrink_games'],20)
        self.assertEqual(calls[-1][1],calls[4][1])

    def test_unobserved_outcomes_cannot_select_winner(self):
        with patch('fantasy_hockey.backtest.experiment',return_value={'runs':[{'paired_delta':None}]*25}):
            with self.assertRaisesRegex(ValueError,'No common complete'):
                run_study({},self.config)


if __name__=='__main__':unittest.main()
