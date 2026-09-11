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
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--teams',type=int,default=14)
    p = commands.add_parser('draft-guide',help='Show fitting picks, positional tiers and review notes')
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--limit',type=int,default=15)
    p.add_argument('--json',action='store_true')


def handle(args):
    if args.command == 'prepare-draft':
        if not 2 <= args.teams <= 32:raise ValueError('Teams must be between 2 and 32')
        if args.output_dir.exists():raise ValueError('Use a new output directory to preserve previous boards')
        result = prepare(read_json(args.board),args.as_of,read_json(args.dossier) if args.dossier else None,args.market)
        result['preparation']['board_sha256'] = hashlib.sha256(args.board.read_bytes()).hexdigest()
        result['preparation']['dossier_sha256'] = hashlib.sha256(args.dossier.read_bytes()).hexdigest() if args.dossier else None
        report = audit(result,args.teams)
        if report['errors']:raise ValueError('; '.join(report['errors']))
        args.output_dir.mkdir(parents=True)
        (args.output_dir/'board.json').write_text(dump_json(result))
        export_csv(result,args.output_dir/'board.csv')
        (args.output_dir/'audit.json').write_text(dump_json(report))
        print(f"Prepared {report['ranked']} estimates, {report['unranked']} unranked players; {report['market_coverage']} market matches.")
        print(args.output_dir)
        return 0
    result = guidance(args.db,args.limit)
    if args.json:print(dump_json(result));return 0
    print(f"{result['teams']} teams | Your slot: {result['slot']} | Next picks: {result['upcoming_picks'][:4]}")
    print(f"Active roster needs: {result['active_needs']}")
    for row in result['candidates']:
        points = '--' if row['projected_points'] is None else f"{float(row['projected_points']):.1f}"
        context = ', '.join(f"{p}: tier {v['tier']} ({v['same_tier_remaining']} left), depth surplus " + ('unknown' if v['active_depth_surplus'] is None else f"{v['active_depth_surplus']:+.1f}") for p,v in row['position_context'].items())
        print(f"{row['id']:14} {row['name']:25} {points:>8} FP | {context}")
        if row.get('market'):print(f"  Market: {row['market']['metric']} {row['market']['value']} ({row['market']['source']})")
        if row['points_per_game'] is not None:
            print(f"  {float(row['projected_games']):.1f} projected appearances; {float(row['points_per_game']):.2f} FP/game; ten fewer appearances: {row['ten_fewer_appearances_point_change']:.1f} FP (scenario only)")
        print('  Review: '+', '.join(row['flags']))
        if row.get('review'):print('  '+row['review']['note']+' | '+row['review']['source'])
    print('Unranked watchlist: '+', '.join(p['name'] for p in result['watchlist']))
    for warning in result['warnings']:print('NOTE: '+warning)
    return 0
