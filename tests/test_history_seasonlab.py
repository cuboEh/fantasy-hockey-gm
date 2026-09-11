from copy import deepcopy
from datetime import date
import csv
import json
from pathlib import Path
import tempfile
import unittest

from fantasy_hockey.backtest import Forecast
from fantasy_hockey.history import assist_ids
from fantasy_hockey.market import load_market
from fantasy_hockey.seasonlab import prepare_history,replay_season,run_year


class HistoricalTests(unittest.TestCase):
    def test_invalid_league_sizes_fail_before_loading_history(self):
        for sizes in ((), (1,), (33,), (14,14)):
            with self.subTest(sizes=sizes), self.assertRaises(ValueError):
                run_year({}, 2025, None, team_counts=sizes)

    def test_assist_formats_and_invalid_serialization(self):
        self.assertEqual(assist_ids('[{"playerId":1},{"playerId":2}]'),['1','2'])
        text='shape: (2,)\nSeries: \'\' [struct[6]]\n[\n{1,{"A"},x}\n{2,{"B"},x}\n]'
        self.assertEqual(assist_ids(json.dumps(text)),['1','2'])
        with self.assertRaises(ValueError):assist_ids('"unknown"')

    def test_history_boundary_and_short_season_normalization(self):
        row={'id':'a','name':'A','position':'C','kind':'skater','team':'X','appeared':True,'points':10,'date':'2021-01-01','game_id':'1'}
        history={2021:{'records':[row],'team_games':{'X':56}},2022:{'records':[{**row,'points':9999}],'team_games':{'X':82}}}
        _,lines=prepare_history(history,2022)
        self.assertAlmostEqual(lines[0][-1][0][1],82/56)
        self.assertAlmostEqual(lines[0][-1][0][2],10*82/56)

    def test_daily_outcomes_cannot_select_starter_or_transaction(self):
        pool={p.id:p for p in [Forecast('a','A','C','skater',10,82,820),Forecast('b','B','C','skater',5,82,410),Forecast('c','C','C','skater',4,82,328)]}
        players={p:{'team':'X'} for p in pool}
        picks=[{'id':'a','team':1,'pick':1},{'id':'b','team':1,'pick':4}]
        season={'source_conflicts':[],'games':{'1':{'date':'2024-10-01','teams':['X','Y']}},
                'records':[{'id':p,'kind':'skater','team':'X','game_id':'1','date':'2024-10-01','points':v,'appeared':True} for p,v in [('a',0),('b',100),('c',200)]]}
        first=replay_season(season,picks,pool,players,{'C':1,'BN':1},1,True)
        altered=deepcopy(season);altered['records'][0]['points']=9999
        second=replay_season(altered,picks,pool,players,{'C':1,'BN':1},1,True)
        self.assertEqual(first['daily_picks'],second['daily_picks'])
        self.assertEqual(first['transactions'],second['transactions'])
        self.assertEqual(first['lineup_points'],0)
        self.assertEqual(next(iter(first['weeks'].values()))['bench'],100)

    def test_market_rejects_future_and_wrong_season(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'market.csv'
            p.write_text('id,season,as_of,source,metric,value\na,20242025,2024-10-01,example,adp,5\n')
            with self.assertRaises(ValueError):load_market(p,'20242025',date(2024,9,1))
            with self.assertRaises(ValueError):load_market(p,'20252026',date(2025,9,1))
            self.assertEqual(load_market(p,'20242025',date(2024,10,1))['a']['value'],5)

class AdditionalPolicyTests(unittest.TestCase):
    def test_round_robin_pairings_include_every_opponent(self):
        from tools.score_matchups import rounds
        for teams in (12,13):
            schedules=rounds(teams)
            for seat in range(1,teams+1):
                opponents=[r[seat] for r in schedules]
                self.assertEqual({p for p in opponents if p is not None},set(range(1,teams+1))-{seat})
                self.assertEqual(opponents.count(None),teams%2)

    def test_prior_calendar_opportunity_penalizes_crowded_nights(self):
        from fantasy_hockey.seasonlab import opportunity_evaluator
        pool=[Forecast('a','A','C','skater',10,82,820),Forecast('b','B','C','skater',9,82,738),Forecast('c','C','C','skater',8,82,656)]
        players={'a':{'team':'X'},'b':{'team':'X'},'c':{'team':'Y'}}
        prior={'games':{'1':{'date':'2024-01-01','teams':['X','Z']},'2':{'date':'2024-01-02','teams':['Y','Z']}}}
        value=opportunity_evaluator(pool,players,prior,{'C':1})
        self.assertEqual(value(pool[1],['a']),0)
        self.assertEqual(value(pool[2],['a']),8)

class NormalizerTests(unittest.TestCase):
    def test_power_play_assists_and_shootout_shutout(self):
        from fantasy_hockey.history import normalize
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            game='2024020001'
            sources={
                'nhl_schedule':[{'game_id':game,'game_type':'R','game_state':'OFF','season_full':'20242025','game_time':'2024-10-01T23:00:00Z','home_team_abbr':'X','away_team_abbr':'Y'}],
                'scoring':[{'game_id':game,'eventId':'1','period_type':'SO','playerId':'x','assists':'[]','strength':'ev','teamAbbrev.default':'X'}],
                'skater_box':[{'game_id':game,'player_id':p,'player_name':p,'team_abbrev':t,'toi':'10:00','goals':'0','assists':'0','plus_minus':'0','shots_on_goal':'2','hits':'0','position':'C'} for p,t in [('x','X'),('y','Y'),('z','X')]],
                'goalie_box':[{'game_id':game,'player_id':p,'player_name':p,'team_abbrev':t,'toi':'65:00','decision':d,'goals_against':'0','saves':'2','shots_against':'2'} for p,t,d in [('gx','X','W'),('gy','Y','L')]]}
            def write():
                for kind,rows in sources.items():
                    with (root/f'{kind}_2025.csv').open('w',newline='') as f:
                        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
            write();weights={'skater':{'goals':6,'power_play_points':2},'goalie':{'shutouts':5,'wins':5}}
            result=normalize(root,2025,weights)
            by_id={r['id']:r for r in result['records']}
            self.assertEqual(by_id['x']['stats']['goals'],0)
            self.assertEqual(by_id['gx']['stats']['shutouts'],1)
            self.assertEqual(by_id['gy']['stats']['shutouts'],1)
            self.assertEqual(by_id['gx']['points'],10)
            sources['scoring'][0].update(period_type='REG',strength='pp',assists='[{"playerId":"z"}]')
            sources['skater_box'][0]['goals']='1';sources['skater_box'][2]['assists']='1'
            sources['goalie_box'][1].update(goals_against='1',shots_against='3')
            write();result=normalize(root,2025,weights);by_id={r['id']:r for r in result['records']}
            self.assertEqual(by_id['x']['stats']['power_play_points'],1)
            self.assertEqual(by_id['z']['stats']['power_play_points'],1)
            self.assertEqual(by_id['gy']['stats']['shutouts'],0)

class MatchupCoverageTests(unittest.TestCase):
    def test_both_policies_use_same_complete_weeks(self):
        from tools.score_matchups import common_weeks
        def side(weeks):return {'record':{'wins':len(weeks),'losses':0,'ties':0,'byes':0,'conflict_weeks_excluded':1},'weeks':[{'week':w,'outcome':'wins'} for w in weeks]}
        fixed,active=common_weeks(side(['a','b']),side(['b','c']))
        self.assertEqual(fixed['weeks'],active['weeks'])
        self.assertEqual(fixed['record']['wins'],1)
        self.assertEqual(active['record']['conflict_weeks_excluded'],2)
