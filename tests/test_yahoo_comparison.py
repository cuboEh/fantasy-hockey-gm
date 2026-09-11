from copy import deepcopy
import unittest
from fantasy_hockey.market import compare_yahoo as compare


class YahooComparisonTests(unittest.TestCase):
    def fixture(self):
        row={'source_row':1,'name':'Elias Pettersson','team_as_pasted':'VAN','positions_as_pasted':['C'],
             'displayed_rank':10,'percent_drafted':3,'numeric_value_1':'120.0','numeric_value_2':'121.0',
             'preseason_adp':120,'adp':121,'extra_tokens':['DTD']}
        source={'season':'20262027','received_date':'2026-09-11','source_url':'user copy',
                'numeric_column_mapping':{'numeric_value_1':'preseason_adp','numeric_value_2':'adp'},'rows':[row]}
        player={'id':'nhl:1','name':'Elias Pettersson','positions':['C'],'team':'VAN','projected_points':'100',
                'projected_games':'50','points_per_game':'2','flags':[]}
        board={'season':'2026-27','as_of':'2026-09-10','players':[player]}
        catalog=[{'id':'nhl:2','name':'Elias Pettersson','positions':['D'],'source':'cached catalog'}]
        return source,board,catalog

    def test_identity_family_market_separation_and_no_mutation(self):
        source,board,catalog=self.fixture();before=deepcopy((source,board,catalog))
        result=compare(source,board,catalog);row=result['rows'][0]
        self.assertEqual(row['id'],'nhl:1')
        self.assertEqual(row['baseline_points'],100)
        self.assertEqual(row['adp_minus_baseline_rank'],120)
        self.assertIn('drafted_in_fewer_than_half_of_reported_drafts',row['warnings'])
        self.assertEqual((source,board,catalog),before)

    def test_missing_stays_missing_and_ambiguous_stays_unresolved(self):
        source,board,catalog=self.fixture()
        for k in ['adp','preseason_adp','numeric_value_1','numeric_value_2','percent_drafted']:source['rows'][0][k]=None
        catalog.append({'id':'nhl:3','name':'Elias Pettersson','positions':['C'],'source':'other'})
        row=compare(source,board,catalog)['rows'][0]
        self.assertIsNone(row['id']);self.assertIsNone(row['adp_minus_baseline_rank'])
        self.assertEqual(row['identity_status'],'ambiguous_identity')

    def test_wrong_season_duplicate_and_mislabeled_values_rejected(self):
        source,board,catalog=self.fixture();source['season']='20252026'
        with self.assertRaisesRegex(ValueError,'Season mismatch'):compare(source,board,catalog)
        source,board,catalog=self.fixture();source['rows']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate source'):compare(source,board,catalog)
        source,board,catalog=self.fixture();source['rows'][0]['adp']=0
        with self.assertRaises(ValueError):compare(source,board,catalog)

    def test_scenarios_are_separate_from_baseline_and_market(self):
        from fantasy_hockey.draft_value import DraftPlayer, Exposure
        from fantasy_hockey.market import attach_scenarios
        source,board,catalog=self.fixture()
        report=compare(source,board,catalog)
        player=DraftPlayer('nhl:1','Elias Pettersson','VAN','skater',('C',),Exposure(60,3),Exposure(40,3))
        attach_scenarios(report,[player])
        row=report['rows'][0]
        self.assertEqual(row['baseline_points'],100)
        self.assertEqual(row['scenario_baseline_points'],180)
        self.assertEqual(row['scenario_downside_points'],120)
        self.assertEqual(row['adp'],121)
