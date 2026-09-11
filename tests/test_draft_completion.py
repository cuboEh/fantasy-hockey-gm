import unittest
from fantasy_hockey.draft_completion import complete_draft
from fantasy_hockey.draft_value import DraftPlayer, Exposure, RosterValue


class CompletionTests(unittest.TestCase):
    def test_completed_rosters_and_fixed_preferences(self):
        calendar={'games':{str(i):{'date':f'2026-10-0{i+5}','teams':['A','B']} for i in range(3)}}
        players=[DraftPlayer(str(i),str(i),'A' if i%2 else 'B',
                            'goalie' if i<4 else 'skater',('G',) if i<4 else ('C',),
                            Exposure(1.5 if i<4 else 3,20-i),Exposure(1.5 if i<4 else 3,20-i),i+1) for i in range(10)]
        slots={'C':1,'G':1,'BN':1}
        value=RosterValue(players,calendar,slots)
        result=complete_draft(players,[],slots,2,1,value,seeds=(10,),width=2)
        for candidate in result['candidates']:
            branch=candidate['branches'][0]
            self.assertEqual(len(branch['picks']),6)
            self.assertEqual(len(set(p['id'] for p in branch['picks'])),6)
            self.assertEqual(len(branch['own_roster']),3)
            self.assertEqual(branch['own_roster'][0],candidate['id'])
            self.assertEqual(branch['value'],value.evaluate(branch['own_roster']))
        self.assertEqual(result,complete_draft(players,[],slots,2,1,value,seeds=(10,),width=2))
        with self.assertRaisesRegex(ValueError,'match'):
            complete_draft(players,[],slots,2,1,value,seeds=(10,),opponent_orders={11:players})


class ComparisonTests(unittest.TestCase):
    def test_pairing_and_duplicate_rejection(self):
        import json
        import tempfile
        from pathlib import Path
        from tools.summarize_draft_comparison import summarize
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'summary.json').write_text('{}')
            (root/'manifest.json').write_text(json.dumps({'seed':1}))
            rows=[{'year':2020,'style':'rank','seat':7,'policy':policy,
                   'common_clean_weeks':20,'common_clean_points':points,
                   'common_clean_failed_weeks':missed}
                  for policy,points,missed in [('coverage_frozen',100,3),('candidate',120,1)]]
            (root/'rows.json').write_text(json.dumps(rows))
            report=summarize([root])['comparisons']['candidate']
            self.assertEqual(report['mean_points_delta'],20)
            self.assertEqual(report['mean_missed_weeks_delta'],-2)
            self.assertEqual(report['season_bootstrap_95_interval'],[20,20])
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                summarize([root,root])
