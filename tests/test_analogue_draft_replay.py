from copy import deepcopy
import unittest
from research.replay_analogue_drafts import corrected_pools,paired_records
from fantasy_hockey.backtest import Forecast
from test_analogues import row


class DraftAnalogueTests(unittest.TestCase):
    def test_future_history_does_not_change_transferred_forecasts(self):
        annual={2024:{'a':row('a')},2025:{'a':row('a',70,50)}}
        base=[Forecast('a','A','C','skater',5,60,300)]
        before=corrected_pools(base,annual,2025,[])
        annual[2025]['a']['games']=999
        self.assertEqual(before,corrected_pools(base,annual,2025,[]))
        self.assertEqual(before[0],base)

    def test_common_matchup_weeks_across_every_variant(self):
        def match(rows):return {'weeks':[{'week':key,'outcome':outcome} for key,outcome in rows]}
        matches=[match([('a','wins'),('b','losses')]),match([('a','losses')]),match([('a','ties'),('c','wins')])]
        original=deepcopy(matches);r=paired_records(matches)
        self.assertEqual(r,[{'wins':1,'ties':0,'weeks':1},{'wins':0,'ties':0,'weeks':1},{'wins':0,'ties':1,'weeks':1}])
        self.assertEqual(matches,original)
