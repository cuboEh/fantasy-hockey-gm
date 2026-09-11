from datetime import date, timedelta
import unittest
from fantasy_hockey.goalie_weeks import weekly_coverage
from fantasy_hockey.providers.nhl_schedule import TEAMS, OPPONENTS, parse_schedule, normalize_club_schedules


class WeeklyGoalieTests(unittest.TestCase):
    def calendar(self, count=3):
        return {'games':{str(i):{'date':f'2026-10-0{i+5}','teams':['A','B']} for i in range(count)}}

    def test_same_team_split_and_minimum(self):
        pair=[{'id':str(i),'team':'A','starts':1.5,'rate':10} for i in range(2)]
        result=weekly_coverage(self.calendar(),pair)[0]
        self.assertEqual(result['expected_starts'],3)
        self.assertEqual(result['failure_probability_proxy'],0)
        self.assertEqual(result['qualified_points'],30)
        pair[0]['starts']=2
        with self.assertRaises(ValueError):weekly_coverage(self.calendar(),pair)

    def test_two_game_tandem_cannot_meet_minimum(self):
        pair=[{'id':str(i),'team':'A','starts':1,'rate':10} for i in range(2)]
        result=weekly_coverage(self.calendar(2),pair)[0]
        self.assertTrue(result['minimum_impossible'])
        self.assertEqual(result['qualified_points'],0)

    def test_three_goalies_use_only_two_slots(self):
        cal=self.calendar()
        for i,g in list(cal['games'].items()):cal['games']['x'+i]={'date':g['date'],'teams':['C','D']}
        gs=[{'id':t,'team':t,'starts':3,'rate':10} for t in ['A','B','C']]
        result=weekly_coverage(cal,gs)[0]
        self.assertEqual(result['expected_starts'],6)
        self.assertEqual(result['collision_days'],3)

    def test_absence_is_contiguous_not_spread(self):
        g={'id':'g','team':'A','starts':1,'rate':10,'first_games_missed':2}
        result=weekly_coverage(self.calendar(),[g])[0]
        self.assertEqual(result['expected_starts'],1)
        self.assertEqual(result['capacity_opportunities'],1)
        with self.assertRaises(ValueError):weekly_coverage(self.calendar(),[{**g,'first_games_missed':-1}])

    def test_calendar_break_week_preserved(self):
        cal={'games':{'a':{'date':'2026-10-05','teams':['A','B']},'b':{'date':'2026-10-19','teams':['A','B']}}}
        weeks=weekly_coverage(cal,[{'id':'a','team':'A','starts':2,'rate':10}])
        self.assertEqual(len(weeks),3)
        self.assertTrue(weeks[1]['minimum_impossible'])


class ScheduleAdapterTests(unittest.TestCase):
    def fixture(self):
        # Synthetic reciprocal schedule: no downloaded source data in tests.
        clubs=list(TEAMS.values()); names={v:k for k,v in TEAMS.items()}; opponents={v:k for k,v in OPPONENTS.items()}
        rows={t:[] for t in clubs}; snapshots={t:{'payload':{'games':[]},'source':'fixture','retrieved_at':'2026-09-10','sha256':'fixture'} for t in clubs}
        for n in range(84):
            day=date(2026,9,29)+timedelta(days=n)
            for i in range(0,32,2):
                home,away=clubs[i:i+2]
                for team,other,prefix in [(home,away,''),(away,home,'AT ')]:
                    rows[team].append(f"{day:%a}. {day:%b} {day.day} 7:00 PM {prefix}{opponents[other]}")
                    snapshots[team]['payload']['games'].append({'id':n*16+i//2,'season':20262027,'gameType':2,
                        'gameDate':day.isoformat(),'startTimeUTC':day.isoformat()+'T23:00:00Z',
                        'homeTeam':{'abbrev':home},'awayTeam':{'abbrev':away}})
        text='\f'.join('2026-27 Schedule for the '+names[t]+'\n'+'\n'.join(rows[t]) for t in clubs)
        return text,snapshots

    def test_complete_pdf_and_api_agree(self):
        text,snapshots=self.fixture()
        pdf=parse_schedule(text);api=normalize_club_schedules(snapshots)
        self.assertEqual(len(pdf['games']),1344)
        self.assertEqual(pdf['team_games'],api['team_games'])

    def test_truncated_pdf_rejected(self):
        text,_=self.fixture()
        with self.assertRaises(ValueError):parse_schedule('\n'.join(text.splitlines()[:-1]))

    def test_api_conflict_and_duplicate_rejected(self):
        _,s=self.fixture()
        s['ANA']['payload']['games'][0]['gameDate']='2026-09-30'
        with self.assertRaises(ValueError):normalize_club_schedules(s)
        _,s=self.fixture();s['ANA']['payload']['games'].append(s['ANA']['payload']['games'][0])
        with self.assertRaises(ValueError):normalize_club_schedules(s)


class ScenarioReportTests(unittest.TestCase):
    def inputs(self):
        from copy import deepcopy
        calendar={'season':'20262027','source_kind':'fixture','games':{'1':{'date':'2026-10-05','teams':['A','B']}}}
        workloads={'season':'2026-27','as_of':'2026-09-10','assumptions':[],
                   'goalies':[{'id':'a','name':'A','team':'A','baseline_starts':1,'downside_starts':.75,
                               'rate':10,'review_status':'unreviewed_or_unallocated','review_by':'2026-09-12',
                               'evidence':{'date':'2026-09-09'}}]}
        return calendar,deepcopy(workloads)

    def test_future_and_missing_workloads_rejected(self):
        from fantasy_hockey.goalie_weeks_cli import report
        c,w=self.inputs()
        with self.assertRaises(ValueError):report(c,w,['a'],'baseline',date(2026,9,8))
        w['goalies'][0]['baseline_starts']=None
        with self.assertRaises(ValueError):report(c,w,['a'],'baseline',date(2026,9,10))

    def test_unknown_role_and_overdue_review_are_visible(self):
        from fantasy_hockey.goalie_weeks_cli import report
        c,w=self.inputs();r=report(c,w,['a'],'baseline',date(2026,9,13))
        self.assertTrue(any('overdue' in x for x in r['warnings']))
        self.assertTrue(any('not source-reviewed' in x for x in r['warnings']))

    def test_physical_capacity_differs_from_selected_lineup(self):
        cal={'games':{str(i):{'date':f'2026-10-0{i+5}','teams':['A','B']} for i in range(2)}}
        goalies=[{'id':'a','team':'A','starts':1,'rate':20},
                 {'id':'b','team':'A','starts':1,'rate':20},
                 {'id':'c','team':'B','starts':1,'rate':1}]
        week=weekly_coverage(cal,goalies)[0]
        self.assertEqual(week['selected_opportunities'],2)
        self.assertEqual(week['capacity_opportunities'],4)
        self.assertFalse(week['minimum_impossible'])
