"""Dated market exports; rankings and ADP never alter projected production."""
import csv
from collections import defaultdict
import hashlib
import json
from math import isfinite
from .board import normalized_name
from datetime import date
from pathlib import Path
from .scoring import number


def load_market(path: Path, season: str, draft_date: date):
    result={}
    with path.open(newline='') as stream:
        reader=csv.DictReader(stream)
        required={'id','season','as_of','source','metric','value'}
        if not required.issubset(reader.fieldnames or []):raise ValueError('Market CSV requires '+', '.join(sorted(required)))
        for row in reader:
            if any(not row.get(k) for k in required):raise ValueError('Market row has missing fields')
            if row['season']!=season or date.fromisoformat(row['as_of'])>draft_date:
                raise ValueError('Market data season/date is incompatible with draft')
            if not row['source'] or row['metric'] not in {'adp','rank'}:
                raise ValueError('Market export needs source and metric adp/rank')
            value=float(number(row['value'],'market value'))
            if value<=0 or row['id'] in result:raise ValueError('Invalid or duplicate market row')
            result[row['id']]={**row,'value':value}
    return result


def compare_market(forecasts, market):
    ranked=sorted(forecasts,key=lambda p:(-p.points,p.id))
    return [{'id':p.id,'name':p.name,'projection_rank':i,'market_value':market[p.id]['value'],
             'metric':market[p.id]['metric'],'rank_gap':market[p.id]['value']-i,
             'source':market[p.id]['source'],'as_of':market[p.id]['as_of'],
             'warning':'Rank disagreement, not calibrated next-pick availability'}
            for i,p in enumerate(ranked,1) if p.id in market]


TEAM_ALIASES={'TB':'TBL','NJ':'NJD','SJ':'SJS','LA':'LAK'}


def season_key(value):
    text=str(value).replace('-','')
    if len(text)==6:text=text[:4]+text[:2]+text[4:]
    if len(text)!=8 or not text.isdigit() or int(text[4:])!=int(text[:4])+1:
        raise ValueError('Invalid season')
    return text


def family(positions):
    positions=set(positions)
    if not positions or positions-{'C','LW','RW','D','G','L','R'}:
        raise ValueError('Invalid positions')
    groups={'G' if p=='G' else 'D' if p=='D' else 'F' for p in positions}
    if len(groups)!=1:raise ValueError('Mixed goalie/defense/forward eligibility')
    return groups.pop()


def numeric(value,label):
    if value is None:return None
    result=float(value)
    if not isfinite(result):raise ValueError('Nonfinite '+label)
    return result


def compare_yahoo(snapshot,board,catalog):
    if season_key(snapshot['season'])!=season_key(board['season']):
        raise ValueError('Season mismatch')
    received=date.fromisoformat(snapshot['received_date'])
    if date.fromisoformat(board['as_of'])>received:raise ValueError('Board follows snapshot receipt')
    if snapshot['numeric_column_mapping']!={'numeric_value_1':'preseason_adp','numeric_value_2':'adp'}:
        raise ValueError('Confirm numeric columns before comparison')
    registry=defaultdict(dict)
    board_by_id={p['id']:p for p in board['players']}
    if len(board_by_id)!=len(board['players']):raise ValueError('Duplicate board ID')
    for p in catalog+[{'id':p['id'],'name':p['name'],'positions':p['positions'],'source':'current baseline board'} for p in board['players']]:
        if not p['id'].startswith('nhl:') or not p['id'][4:].isdigit():raise ValueError('Invalid NHL identity')
        key=(normalized_name(p['name']),family(p['positions']))
        registry[key].setdefault(p['id'],set()).add(p['source'])
    supported=[p for p in board['players'] if numeric(p.get('projected_points'),'baseline points') is not None]
    ranked=sorted(supported,key=lambda p:(-float(p['projected_points']),p['id']))
    ranks={p['id']:i for i,p in enumerate(ranked,1)}
    seen_names=set();seen_ids=set();rows=[]
    for original in snapshot['rows']:
        key=(normalized_name(original['name']),family(original['positions_as_pasted']))
        if key in seen_names:raise ValueError('Duplicate source player')
        seen_names.add(key)
        candidates=registry.get(key,{})
        pid=next(iter(candidates)) if len(candidates)==1 else None
        if pid in seen_ids:raise ValueError('Multiple source rows resolve to one NHL ID')
        if pid:seen_ids.add(pid)
        p=board_by_id.get(pid)
        adp=numeric(original['adp'],'ADP');pre=numeric(original['preseason_adp'],'preseason ADP')
        pct=numeric(original['percent_drafted'],'drafted percentage')
        if any(v is not None and v<=0 for v in (adp,pre)):raise ValueError('ADP must be positive')
        if pct is not None and not 0<=pct<=100:raise ValueError('Drafted percentage outside bounds')
        if numeric(original['numeric_value_1'],'raw preseason ADP')!=pre or numeric(original['numeric_value_2'],'raw ADP')!=adp:
            raise ValueError('Labeled ADP differs from original values')
        positions=original['positions_as_pasted'];warnings=[]
        status='matched' if pid else 'ambiguous_identity' if candidates else 'unmatched_identity'
        if not pid:warnings.append(status)
        if not p:warnings.append('missing_baseline_player')
        elif p['projected_points'] is None:warnings.append('missing_projection')
        if adp is None:warnings.append('missing_adp')
        # This threshold is a review flag, not a fitted availability probability.
        if pct is not None and pct<50:warnings.append('drafted_in_fewer_than_half_of_reported_drafts')
        if original['extra_tokens']:warnings.append('Yahoo_status_requires_review')
        team=TEAM_ALIASES.get(original['team_as_pasted'],original['team_as_pasted'])
        differs=bool(p and set(p['positions'])!=set(positions))
        team_differs=bool(p and TEAM_ALIASES.get(p['team'],p['team'])!=team)
        if team_differs:warnings.append('team_conflict_review')
        if p:warnings.extend(flag for flag in p.get('flags',[]) if flag!='eligibility_unverified')
        rank=ranks.get(pid)
        rows.append({'source_row':original['source_row'],'name':original['name'],'id':pid,
                     'identity_status':status,'identity_candidates':sorted(candidates),
                     'identity_sources':sorted(candidates.get(pid,[])),
                     'yahoo_team':original['team_as_pasted'],'board_team':p['team'] if p else None,
                     'team_differs':team_differs,'yahoo_positions':','.join(positions),
                     'board_positions':','.join(p['positions']) if p else None,'eligibility_differs':differs,
                     'yahoo_status':','.join(original['extra_tokens']),
                     'displayed_yahoo_rank':original['displayed_rank'],
                     'preseason_adp':pre,'adp':adp,'percent_drafted':pct,
                     'baseline_rank':rank,'baseline_points':numeric(p['projected_points'],'baseline points') if p else None,
                     'projected_games':numeric(p['projected_games'],'projected games') if p else None,
                     'points_per_game':numeric(p['points_per_game'],'points per game') if p else None,
                     'adp_minus_baseline_rank':adp-rank if adp is not None and rank is not None else None,
                     'review_note':p.get('review',{}).get('note','') if p else '',
                     'warnings':sorted(set(warnings))})
    return {'season':snapshot['season'],'received_date':snapshot['received_date'],'source_url':snapshot['source_url'],
            'valuation_basis':'Unchanged historical-rate season-total baseline; not current context scenarios, usable games or positional replacement value',
            'rank_scope':f'All {len(ranked)} projected players in the {len(board_by_id)}-player baseline board; incomplete player coverage',
            'identity_basis':'Unique normalized full name plus forward/defense/goalie family in cached NHL-ID catalogs. Not an authenticated Yahoo-ID crosswalk.',
            'eligibility_basis':'Yahoo positions supplied by user for confirmed season; differences reviewed by valid position family, not independently fetched',
            'adp_interpretation':'Aggregate market average, not next-turn survival probability; drafted percentage is retained separately',
            'rows':rows,'summary':{'rows':len(rows),'matched':sum(r['identity_status']=='matched' for r in rows),
              'with_adp':sum(r['adp'] is not None for r in rows),'with_projection':sum(r['baseline_points'] is not None for r in rows),
              'missing_baseline':sum(r['id'] not in board_by_id for r in rows),'eligibility_differences':sum(r['eligibility_differs'] for r in rows),
              'team_conflicts':sum(r['team_differs'] for r in rows)}}



def attach_scenarios(report,players):
    """Expose existing conditional estimates without changing baseline or Yahoo values."""
    values={p.id:{case:(getattr(p,case).games*getattr(p,case).rate if getattr(p,case) else None)
                  for case in ('baseline','downside')} for p in players}
    ranks={pid:i for i,(pid,_) in enumerate(sorted(
        ((pid,v['baseline']) for pid,v in values.items() if v['baseline'] is not None),
        key=lambda pair:(-pair[1],pair[0])),1)}
    for row in report['rows']:
        v=values.get(row['id'],{})
        row['scenario_baseline_points']=v.get('baseline')
        row['scenario_downside_points']=v.get('downside')
        row['scenario_baseline_rank']=ranks.get(row['id'])
        row['adp_minus_scenario_rank']=row['adp']-ranks[row['id']] if row['adp'] is not None and row['id'] in ranks else None
    report['scenario_basis']='Existing reviewed goalie starts times shrunken starter rates and explicitly selected skater cases. Conditional season totals, not probabilities or usable-game/replacement values.'
    report['scenario_rank_scope']=f'All {len(ranks)} supported scenario players in the supplied baseline board'


def register(commands):
    parser=commands.add_parser('compare-market',help='Compare user-supplied Yahoo ADP with existing valuations')
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--board',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,nargs='+',required=True,help='Cached MoneyPuck player CSVs used only for NHL identity')
    parser.add_argument('--output-dir',type=Path,required=True)
    for name in ('workloads','rates','context','case-map'):parser.add_argument('--'+name,type=Path)


def handle(args):
    if bool(args.workloads)!=bool(args.rates):raise ValueError('Supply both workloads and rates')
    if bool(args.context)!=bool(args.case_map) or (args.context and not args.workloads):raise ValueError('Context needs case map and workload inputs')
    if args.output_dir.exists():raise ValueError('Use a new output directory')
    catalog=[]
    for path in args.catalog:
        with path.open() as stream:
            for row in csv.DictReader(stream):
                catalog.append({'id':'nhl:'+row['playerId'],'name':row['name'],
                                'positions':[row['position']],'source':str(path)})
    report=compare_yahoo(json.loads(args.snapshot.read_text()),json.loads(args.board.read_text()),catalog)
    paths=[args.snapshot,args.board,*args.catalog,Path(__file__)]
    if args.workloads:
        from fantasy_hockey.decision_cli import build_players
        files={name:getattr(args,name) for name in ('workloads','rates','context','case_map') if getattr(args,name)}
        inputs={name:json.loads(path.read_text()) for name,path in files.items()}
        players,notes=build_players(json.loads(args.board.read_text()),inputs['workloads'],inputs['rates'],date.fromisoformat(report['received_date']),inputs.get('context'),inputs.get('case_map'))
        attach_scenarios(report,players)
        for row in report['rows']:
            row['scenario_notes']=notes.get(row['id'],{})
        paths.extend(files.values())
        paths.extend(Path(__file__).parent.glob('*.py'))
    report['input_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.output_dir.mkdir(parents=True)
    (args.output_dir/'comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    columns=[k for k in report['rows'][0] if k not in {'identity_candidates','identity_sources','scenario_notes'}]
    with (args.output_dir/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for row in report['rows']:
            writer.writerow({k:'; '.join(row[k]) if isinstance(row[k],list) else row[k] for k in columns})
    review=[r for r in report['rows'] if r['eligibility_differs'] or r['identity_status']!='matched' or r['team_differs'] or r['baseline_points'] is None]
    (args.output_dir/'identity-eligibility-review.json').write_text(json.dumps(review,indent=2,ensure_ascii=False))
    missing=[r for r in report['rows'] if r['baseline_points'] is None]
    lines=['# Yahoo market comparison', '',report['valuation_basis'], '',report['rank_scope'], '',
           'Positive ADP gap means a player goes later than this baseline rank. It does not prove a bargain.',
           'Status and source warnings must be reviewed. Blank CSV fields are missing, not zero.', '',
           '## Largest disagreements among players drafted at least 50% of the time', '',
           'This filter limits low-participation distortion; it is not a confidence estimate.']
    qualified=[r for r in report['rows'] if r['adp_minus_baseline_rank'] is not None and (r['percent_drafted'] or 0)>=50]
    for title,direction in [('Model ranks earlier than ADP',1),('Market drafts earlier than model rank',-1)]:
        lines+=['',f'### {title}','','| Player | Positions | Baseline rank | ADP | Drafted | Gap | Review flags |','| --- | --- | ---: | ---: | ---: | ---: | --- |']
        selected=[r for r in qualified if r['adp_minus_baseline_rank']*direction>0]
        for row in sorted(selected,key=lambda r:(-direction*r['adp_minus_baseline_rank'],r['name']))[:12]:
            lines.append(f"| {row['name']} | {row['yahoo_positions']} | {row['baseline_rank']} | {row['adp']:.1f} | {row['percent_drafted']:.0f}% | {row['adp_minus_baseline_rank']:+.1f} | {'; '.join(row['warnings'])} |")
    if 'scenario_basis' in report:
        lines+=['','## Existing reviewed scenarios', '',report['scenario_basis'],'',report['scenario_rank_scope'],'',
                'The CSV includes scenario values for every matched supported player. Examples with large historical-versus-scenario rank changes:', '',
                '| Player | Historical rank | Scenario rank | ADP | Baseline case FP | Downside case FP |',
                '| --- | ---: | ---: | ---: | ---: | ---: |']
        changed=[r for r in qualified if r.get('scenario_baseline_rank') is not None]
        for r in sorted(changed,key=lambda r:-abs(r['baseline_rank']-r['scenario_baseline_rank']))[:12]:
            lines.append(f"| {r['name']} | {r['baseline_rank']} | {r['scenario_baseline_rank']} | {r['adp']:.1f} | {r['scenario_baseline_points']:.1f} | {r['scenario_downside_points']:.1f} |")
    lines+=['','## Missing production estimates','','These players remain in the comparison without invented values.','']
    for r in missing:lines.append(f"- {r['name']}: ADP {r['adp'] if r['adp'] is not None else 'missing'}; drafted {r['percent_drafted'] if r['percent_drafted'] is not None else 'missing'}%")
    (args.output_dir/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(report['summary'],indent=2))
    print(args.output_dir/'comparison.csv')

    return 0
