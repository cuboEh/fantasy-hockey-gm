from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from fantasy_hockey.gm_advice import assign_all, compare_pickup, lineups
from fantasy_hockey.gm_state import validate_snapshot
from test_gm import snapshot, NOW


def decision_snapshot(now=NOW):
    p=snapshot(now);i=p['inputs'];settings=i['settings']['data']
    settings['config']['roster']={'C':1,'LW':1,'G':1,'BN':2,'IR+':1}
    settings['matchup']={'start':now.date().isoformat(),'end':(now+timedelta(days=2)).date().isoformat()}
    settings['rules'].update(lock_benched_players=False,waiver_mode='standard',goalie_minimum=2)
    def component(value):
        c=deepcopy(i['roster']);c['data']=value;return c
    def player(pid,positions,slot,team='AAA'):
        return {'id':pid,'name':pid,'positions':positions,'selected_position':slot,'nhl_team':team,
                'can_drop':True,'injury_slots':[]}
    roster=[player('center',['C'],'C'),player('wing',['LW'],'LW'),
            player('flex',['C','LW'],'BN'),player('goalie',['G'],'G','BBB')]
    i['roster']['data']=roster
    i['players']=component(roster+[player('pickup',['C'],None),player('weak',['C'],None)])
    i['availability']['data']=[{'id':r['id'],'state':'owned' if r in roster else 'free_agent',
        'owner_team_id':p['team']['id'] if r in roster else None,'waiver_clears_at':None}
        for r in i['players']['data']]
    i['schedule']['data']=[{'id':'game'+str(n),'teams':['AAA','BBB'],
        'starts_at':(now+timedelta(hours=2,days=n)).isoformat()} for n in range(3)]
    i['schedule_coverage']=component({'start':(now-timedelta(days=1)).isoformat(),
        'end':(now+timedelta(days=4)).isoformat(),'teams':['AAA','BBB']})
    i['goalie_results']=component([])
    i['player_status']['data']=[{'id':r['id'],'status':'available','confirmed':True} for r in i['players']['data']]
    forecasts=[]
    for r,points in zip(i['players']['data'],[2,3,8,-2,12,1]):
        goalie=r['positions']==['G']
        forecasts.append({'id':r['id'],'data_type':'projection','model_version':'fixture-1','model_role':'working',
            'kind':'goalie' if goalie else 'skater','source':'Fictional dated projection',
            'issued_at':(now-timedelta(hours=1)).isoformat(),'training_end':(now-timedelta(days=1)).isoformat(),
            'horizon_start':now.isoformat(),'horizon_end':(now+timedelta(days=4)).isoformat(),
            'history':None,'rates':{'wins':0,'goals_against':1} if goalie else {'goals':points/5,'shots_on_goal':0},
            'games':[{'game_id':g['id'],'starts_at':g['starts_at'],'expected_appearances':1,
                'participation':'projected','basis':'Fictional workload assumption'} for g in i['schedule']['data']],
            'assumptions':['Fixture only'],'missing_inputs':[]})
    i['forecasts']=component(forecasts)
    return validate_snapshot(p,p['league']['id'],p['team']['id'],now)


class AdviceTests(unittest.TestCase):
    def test_collision_and_negative_goalie_with_real_bench_capacity(self):
        p=decision_snapshot();result=lineups(p,NOW);d=result['days'][0]
        self.assertEqual(d['points'],11)
        self.assertEqual(d['assignments']['flex'],'C')
        self.assertEqual(d['assignments']['goalie'],'BN')
        self.assertEqual(d['gain'],8)
        self.assertEqual(result['goalie']['confirmed_earned'],0)
        self.assertEqual(result['goalie']['remaining_required'],2)
        self.assertEqual(len(d['bench']),2)
        p['inputs']['settings']['data']['config']['roster']['BN']=1
        result=lineups(p,NOW);d=result['days'][0]
        self.assertEqual(d['points'],9)  # Negative goalie forced into active slot by capacity.
        self.assertEqual(d['goalie_negative_exposure'],['goalie'])

    def test_locked_active_and_bench_cannot_be_promoted_after_start(self):
        p=decision_snapshot();later=NOW+timedelta(hours=2)
        d=lineups(p,later)['days'][0]
        self.assertEqual(d['assignments']['center'],'C')
        self.assertEqual(d['assignments']['flex'],'BN')
        self.assertEqual(d['points'],0)  # Started points are not future production.
        self.assertEqual(len(d['locked_player_ids']),4)

    def test_unknown_goalie_keeps_supported_skater_changes(self):
        p=decision_snapshot()
        next(r for r in p['inputs']['forecasts']['data'] if r['id']=='goalie')['games'][0]['expected_appearances']=None
        result=lineups(p,NOW);d=result['days'][0]
        self.assertEqual(result['status'],'partial')
        self.assertEqual(d['assignments']['goalie'],'G')
        self.assertEqual(d['assignments']['flex'],'C')
        self.assertTrue(any('Participation' in r for r in d['reasons']))

    def test_missing_coverage_assignment_stale_and_failed_refresh_restrict(self):
        for change in ('coverage','assignment','expired','error'):
            p=decision_snapshot();error=None
            if change=='coverage':p['inputs']['schedule_coverage']['data']['teams']=['AAA']
            if change=='assignment':p['inputs']['roster']['data'][0]['selected_position']=None
            if change=='expired':p['inputs']['roster']['expires_at']=NOW.isoformat()
            if change=='error':error='Interrupted'
            with self.subTest(change=change):self.assertEqual(lineups(p,NOW,last_error=error)['status'],'restricted')

    def test_pickup_values_whole_roster_and_reports_long_term_gap(self):
        p=decision_snapshot();before=deepcopy(p)
        result=compare_pickup(p,NOW,'pickup','center')
        self.assertEqual(result['status'],'comparison')
        self.assertEqual(result['net_points'],27)  # flex shifts to LW, displacing wing as well.
        self.assertEqual(result['lost_usable_points'],0)
        self.assertEqual(result['decision'],'review')
        self.assertIsNone(result['rest_of_season'])
        self.assertEqual(p,before)
        self.assertEqual(compare_pickup(p,NOW,'weak','flex')['decision'],'keep_roster')

    def test_transaction_restrictions(self):
        for mode in ('limit','cant_cut','waiver','unknown','owned'):
            p=decision_snapshot()
            if mode=='limit':p['inputs']['settings']['data']['rules']['acquisitions_used']=4
            if mode=='cant_cut':p['inputs']['roster']['data'][0]['can_drop']=None
            if mode in ('waiver','unknown','owned'):
                r=next(r for r in p['inputs']['availability']['data'] if r['id']=='pickup')
                r['state']={'waiver':'waivers','unknown':'unknown','owned':'owned'}[mode]
                if mode=='owned':r['owner_team_id']='other'
            with self.subTest(mode=mode):self.assertEqual(compare_pickup(p,NOW,'pickup','center')['status'],'restricted')

    def test_injury_slot_is_held_and_does_not_create_regular_vacancy(self):
        p=decision_snapshot();r=p['inputs']['roster']['data'][0]
        r['selected_position']='IR+';r['injury_slots']=['IR+']
        result=lineups(p,NOW)
        self.assertEqual(result['days'][0]['assignments']['center'],'IR+')
        self.assertEqual(compare_pickup(p,NOW,'pickup','center')['status'],'restricted')

    def test_timezone_midnight_requires_new_actual_lineup(self):
        p=decision_snapshot();later=NOW+timedelta(hours=13)
        for c in p['inputs'].values():c['expires_at']=(later+timedelta(hours=4)).isoformat()
        result=lineups(p,later)
        self.assertEqual(result['status'],'restricted')
        self.assertTrue(any('observed today' in r for r in result['reasons']))

    def test_goalie_qualification_alternative_exposes_cost_without_guarantee(self):
        result=lineups(decision_snapshot(),NOW)
        self.assertEqual(result['goalie']['alternative_expected'],3)
        self.assertEqual(result['goalie']['alternative_point_cost'],6)
        alt=result['days'][0]['goalie_alternative']
        self.assertEqual(alt['assignments']['goalie'],'G')
        self.assertEqual(alt['points'],9)

    def test_partial_matchup_counts_only_confirmed_earned_and_remaining_games(self):
        p=decision_snapshot()
        old={'id':'past','teams':['AAA','BBB'],'starts_at':(NOW-timedelta(hours=3)).isoformat()}
        p['inputs']['schedule']['data'].append(old)
        p['inputs']['goalie_results']['data']=[{'id':'earned','player_id':'goalie','game_id':'past','qualified':True,'confirmed':True}]
        result=lineups(p,NOW)
        self.assertEqual(result['goalie']['confirmed_earned'],1)
        self.assertEqual(result['goalie']['remaining_required'],1)
        self.assertEqual(result['days'][0]['points'],3)  # Started active assignments held: center 2 + wing 3 - goalie 2.

    def test_rest_of_season_loss_prevents_short_term_drop_recommendation(self):
        p=decision_snapshot();i=p['inputs'];settings=i['settings']['data']
        settings['league_details']={'season_end':(NOW+timedelta(days=5)).date().isoformat()}
        i['schedule_coverage']['data'].update(end=(NOW+timedelta(days=7)).isoformat(),teams=['AAA','BBB','CCC','DDD'])
        i['schedule']['data'][0]['teams']=['AAA','CCC']
        for n in (3,4,5):
            i['schedule']['data'].append({'id':'late'+str(n),'teams':['CCC','DDD'],
                'starts_at':(NOW+timedelta(days=n,hours=2)).isoformat()})
        for r in i['roster']['data']+i['players']['data']:
            if r['id']=='center':r['nhl_team']='CCC'
        teams={r['id']:r['nhl_team'] for r in i['players']['data']}
        for f in i['forecasts']['data']:
            f['horizon_end']=(NOW+timedelta(days=7)).isoformat()
            if f['id'] in ('center','weak','flex'):
                f['rates']={'goals':{'center':2,'weak':0.8,'flex':0}[f['id']],'shots_on_goal':0}
            f['games']=[{'game_id':g['id'],'starts_at':g['starts_at'],'expected_appearances':1,
                'participation':'projected','basis':'Fixture'} for g in i['schedule']['data'] if teams[f['id']] in g['teams']]
        validate_snapshot(p,'demo-league','demo-team',NOW)
        result=compare_pickup(p,NOW,'weak','center')
        self.assertEqual(result['net_points'],2)
        self.assertEqual(result['rest_of_season']['net_points'],-28)
        self.assertTrue(result['rest_of_season']['overlaps_matchup'])
        self.assertEqual(result['decision'],'keep_roster')

    def test_three_usable_games_beat_four_colliding_games(self):
        p=decision_snapshot();i=p['inputs'];i['settings']['data']['matchup']['end']=(NOW+timedelta(days=6)).date().isoformat()
        i['schedule_coverage']['data'].update(end=(NOW+timedelta(days=8)).isoformat(),teams=['AAA','BBB','CCC','DDD'])
        i['schedule']['data']=[{'id':str(n),'teams':['AAA','BBB'] if n%2==0 else ['CCC','DDD'],
            'starts_at':(NOW+timedelta(days=n,hours=2)).isoformat()} for n in range(7)]
        for r in i['players']['data']:
            if r['id']=='weak':r.update(nhl_team='CCC',positions=['LW'])
        teams={r['id']:r['nhl_team'] for r in i['players']['data']}
        for f in i['forecasts']['data']:
            f['horizon_end']=(NOW+timedelta(days=8)).isoformat()
            if f['id']=='pickup':f['rates']={'goals':0.4,'shots_on_goal':0}
            if f['id']=='weak':f['rates']={'goals':0.4,'shots_on_goal':0}
            f['games']=[{'game_id':g['id'],'starts_at':g['starts_at'],'expected_appearances':1,
                'participation':'projected','basis':'Fixture'} for g in i['schedule']['data'] if teams[f['id']] in g['teams']]
        validate_snapshot(p,'demo-league','demo-team',NOW)
        collision=compare_pickup(p,NOW,'pickup','center')
        off_night=compare_pickup(p,NOW,'weak','center')
        self.assertEqual(collision['net_points'],0)
        self.assertEqual(off_night['net_points'],6)
        self.assertEqual(collision['added_usable_points'],0)
        self.assertEqual(off_night['added_usable_points'],6)

    def test_vacant_regular_and_direct_injury_slot_adds(self):
        p=decision_snapshot()
        self.assertEqual(compare_pickup(p,NOW,'pickup')['status'],'comparison')
        # Make the regular roster full and verify the supplied direct-injury rule.
        p['inputs']['settings']['data']['config']['roster']['BN']=1
        candidate=next(r for r in p['inputs']['players']['data'] if r['id']=='pickup')
        candidate['injury_slots']=['IR+']
        self.assertEqual(compare_pickup(p,NOW,'pickup')['status'],'restricted')
        p['inputs']['settings']['data']['rules']['allow_direct_injury_slot_adds']=True
        result=compare_pickup(p,NOW,'pickup')
        self.assertEqual(result['status'],'comparison')
        self.assertEqual(result['resulting_roster']['days'][0]['assignments']['pickup'],'IR+')
        self.assertEqual(result['net_points'],0)

    def test_already_started_candidate_can_only_join_bench_today(self):
        p=decision_snapshot();later=NOW+timedelta(hours=2)
        result=compare_pickup(p,later,'pickup','flex')
        self.assertEqual(result['status'],'comparison')
        self.assertEqual(result['resulting_roster']['days'][0]['assignments']['pickup'],'BN')
        self.assertEqual(result['resulting_roster']['days'][0]['points'],0)
