"""Local preparation commands; no external account access."""
from datetime import date
import hashlib
from pathlib import Path

from .board import read_json, dump_json, export_csv
from .preparation import prepare, audit, guidance


def register(commands):
    p = commands.add_parser('prepare-draft',help='Create a reviewed board and audit without overwriting a session')
    p.add_argument('--board',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--dossier',type=Path)
    p.add_argument('--market',type=Path)
    p.add_argument('--projection-workbook',type=Path,help='Permitted DtZ XLSX snapshot, cached stat values only')
    p.add_argument('--require-reviewed-projections',action='store_true',help='Limit recommendations to Yahoo eligibility and supplied projections')
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--teams',type=int,default=14)
    p = commands.add_parser('draft-guide',help='Show fitting picks, positional tiers and review notes')
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--limit',type=int,default=15)
    p.add_argument('--json',action='store_true')
    p.add_argument('--goalie-workloads',type=Path,help='Dated goalie role and workload review JSON')
    p.add_argument('--goalie-calendar',type=Path,help='Completed historical schedule JSON for experimental goalie insurance estimates')


def handle(args):
    if args.command == 'prepare-draft':
        if not 2 <= args.teams <= 32:raise ValueError('Teams must be between 2 and 32')
        if args.output_dir.exists():raise ValueError('Use a new output directory to preserve previous boards')
        result = prepare(read_json(args.board),args.as_of,read_json(args.dossier) if args.dossier else None,args.market)
        projection_report = None
        if args.projection_workbook:
            from .providers.dtz import projection_dossier
            manifest = read_json(args.projection_workbook.parent/'metadata.json')
            workbook_hash = hashlib.sha256(args.projection_workbook.read_bytes()).hexdigest()
            if (manifest['season'] != result['season'] or date.fromisoformat(manifest['received_date']) > args.as_of
                    or manifest['sha256'] != workbook_hash):
                raise ValueError('Projection snapshot manifest season/date/hash mismatch')
            projections, projection_report = projection_dossier(args.projection_workbook,result,date.fromisoformat(manifest['received_date']))
            if not projections:raise ValueError('No valid independent projections matched')
            metadata = result['preparation']
            result = prepare(result,args.as_of,{'projections':projections})
            result['preparation'] = metadata
            result['preparation']['projection_workbook_sha256'] = workbook_hash
            result['preparation']['projection_manifest_sha256'] = hashlib.sha256((args.projection_workbook.parent/'metadata.json').read_bytes()).hexdigest()
            result['working_valuation'] = 'DtZ complete stat projections scored with league weights; historical fallback is restricted when reviewed projections are required'
            result['historical_baseline_metadata'] = {k:result[k] for k in ('model','source','source_generated','warnings')}
            result['model'] = 'mvp1_dtz_league_points_v1'
            result['warnings'] = ['Unvalidated independent preseason projections, not a demonstrated predictive advantage',
                                  'Yahoo market and eligibility are a user-supplied dated snapshot; verify material changes before drafting',
                                  'Historical-only and eligibility-unverified players are searchable but restricted when reviewed projections are required',
                                  'Role and injury scenarios are comparisons, not a second adjustment to provider projections']
        if args.require_reviewed_projections:
            result['recommendation_policy'] = 'yahoo_and_supplied_projection'
        result['preparation']['board_sha256'] = hashlib.sha256(args.board.read_bytes()).hexdigest()
        result['preparation']['dossier_sha256'] = hashlib.sha256(args.dossier.read_bytes()).hexdigest() if args.dossier else None
        report = audit(result,args.teams)
        if report['errors']:raise ValueError('; '.join(report['errors']))
        args.output_dir.mkdir(parents=True)
        (args.output_dir/'board.json').write_text(dump_json(result))
        export_csv(result,args.output_dir/'board.csv')
        (args.output_dir/'audit.json').write_text(dump_json(report))
        if projection_report is not None:
            (args.output_dir/'projection-import.json').write_text(dump_json(projection_report))
        print(f"Prepared {report['ranked']} estimates, {report['unranked']} unranked players; {report['market_coverage']} market matches.")
        print(args.output_dir)
        return 0
    result = guidance(args.db,args.limit,goalie_calendar=args.goalie_calendar,goalie_workloads=args.goalie_workloads)
    if args.json:print(dump_json(result));return 0
    print(f"{result['teams']} teams | Your slot: {result['slot']} | Next picks: {result['upcoming_picks'][:4]}")
    print(f"Active roster needs: {result['active_needs']}")
    coverage = result['goalie_coverage']
    if coverage:
        print('Goalie coverage: '+coverage.get('interpretation', coverage.get('reason', '')))
        if not coverage['slot_known']:print('Set your draft slot to evaluate your owned goalie coverage.')
        elif coverage.get('owned_goalies', 0):
            for candidate in coverage['candidates'][:5]:
                print(f"  {candidate['name']}: {candidate['insurance_points']:.1f} proxy insurance FP, check roster fit")
    for row in result['candidates']:
        points = '--' if row['projected_points'] is None else f"{float(row['projected_points']):.1f}"
        context = ', '.join(f"{p}: tier {v['tier']} ({v['same_tier_remaining']} left), depth surplus " + ('unknown' if v['active_depth_surplus'] is None else f"{v['active_depth_surplus']:+.1f}") for p,v in row['position_context'].items())
        print(f"{row['id']:14} {row['name']:25} {points:>8} FP | {context}")
        if row.get('market'):print(f"  Market: {row['market']['metric']} {row['market']['value']} ({row['market']['source']})")
        if row.get('yahoo'):
            y = row['yahoo']
            print(f"  Yahoo rank {y.get('rank')}; preseason ADP {y.get('preseason_adp')}; drafted {y.get('percent_drafted')}%; status {y.get('status') or 'none supplied'}")
        if row.get('projection_evidence'):print('  Working forecast: '+row['projection_evidence']['source'])
        if row.get('baseline_projection',{}).get('projected_points') is not None:
            print(f"  Historical baseline comparison: {float(row['baseline_projection']['projected_points']):.1f} FP; disagreement is not a proven edge")
        if row['points_per_game'] is not None:
            print(f"  {float(row['projected_games']):.1f} projected appearances; {float(row['points_per_game']):.2f} FP/game; ten fewer appearances: {row['ten_fewer_appearances_point_change']:.1f} FP (scenario only)")
        if row.get('goalie_workload_review'):
            review = row['goalie_workload_review']
            print(f"  Workload review: {review['review_status']}; baseline/downside start scenarios: {review['baseline_starts']}/{review['downside_starts']}. Analyst assumptions, not reported projections.")
            if review.get('role'):print(f"  Role: {review['role']}; health: {review.get('health_status', 'not assessed')}; recheck by {review['review_by']}")
            if review.get('evidence'):print('  '+review['evidence']['fact']+' | '+review['evidence']['source'])
        print('  Review: '+', '.join(row['flags']))
        if row.get('review'):print('  '+row['review']['note']+' | '+row['review']['source'])
        reference = row.get('review',{}).get('reference_scenarios')
        if reference and reference.get('baseline_points') is not None:
            print(f"  Earlier independent scenario comparison: {float(reference['baseline_points']):.1f}/{float(reference['downside_points']):.1f} FP baseline/downside; analyst cases, not forecast confidence bounds")
        for old in row.get('review_history',[]):print('  Earlier review: '+old['note'])
        for pos, alternatives in row['later_market_alternatives'].items():
            if alternatives:print('  Later '+pos+' comparisons: '+ '; '.join(f"{q['name']} (ADP {q['adp']}, {q['points_cost']:+.1f} FP cost)" for q in alternatives))
    print('Best fitting option by position:')
    for pos,p in result['position_options'].items():
        print('  '+pos+': '+(f"{p['name']}, {float(p['projected_points']):.1f} FP, ADP {(p.get('market') or {}).get('value','unknown')}" if p else 'none supported'))
    print(f"Restricted watchlist: {len(result['watchlist'])} players, showing first 10 by known market cost")
    for p in result['watchlist'][:10]:print('  '+p['name']+': '+ '; '.join(p['restrictions']))
    for warning in result['warnings']:print('NOTE: '+warning)
    return 0
