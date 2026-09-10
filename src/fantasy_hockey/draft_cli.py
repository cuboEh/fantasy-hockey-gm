"""CLI entry points for board construction and manual draft operations."""

from datetime import date
import hashlib
from pathlib import Path

from .board import build_board, dump_json, export_csv, number
from .config import load_config
from . import draft


def register(commands) -> None:
    build = commands.add_parser('build-board', help='Score a labeled historical baseline for real players')
    build.add_argument('--config',type=Path,required=True)
    build.add_argument('--input',type=Path,required=True)
    build.add_argument('--as-of',type=date.fromisoformat,required=True)
    build.add_argument('--moneypuck-dir',type=Path)
    build.add_argument('--overrides',type=Path)
    build.add_argument('--output',type=Path,required=True)
    build.add_argument('--csv',type=Path)
    command = commands.add_parser('draft',help='Local manual snake draft tracker')
    actions = command.add_subparsers(dest='action',required=True)
    for action in ['init','board','pick','undo','set-slot','positions','export']:
        sub = actions.add_parser(action)
        sub.add_argument('--db',type=Path,required=True)
        if action=='init':
            sub.add_argument('--board',type=Path,required=True)
            sub.add_argument('--teams',type=int,required=True)
            sub.add_argument('--slot',type=int)
        elif action=='board':
            sub.add_argument('--search',default='')
            sub.add_argument('--position',choices=['C','LW','RW','D','G'])
            sub.add_argument('--limit',type=int,default=20)
            sub.add_argument('--json',action='store_true')
        elif action in ['pick','positions']:
            sub.add_argument('player',help='NHL ID, full name or unambiguous partial name')
            if action=='positions':
                sub.add_argument('--eligible',required=True,help='Comma-separated positions, for example C,LW')
                sub.add_argument('--note',required=True)
        elif action=='set-slot':
            sub.add_argument('slot',type=int)
        elif action=='export':
            sub.add_argument('--output',type=Path,required=True)


def handle(args) -> int:
    if args.command=='build-board':
        inputs = {args.input.resolve(),args.config.resolve()}
        if args.overrides:
            inputs.add(args.overrides.resolve())
        if args.output.resolve() in inputs or (args.csv and args.csv.resolve() in inputs):
            raise ValueError('Output cannot overwrite an input')
        if args.csv and args.output.resolve()==args.csv.resolve():
            raise ValueError('JSON and CSV outputs must have different paths')
        board = build_board(args.input,load_config(args.config),args.as_of,args.moneypuck_dir,args.overrides)
        board['config_sha256'] = hashlib.sha256(args.config.read_bytes()).hexdigest()
        board['overrides_sha256'] = hashlib.sha256(args.overrides.read_bytes()).hexdigest() if args.overrides else None
        board['moneypuck_sha256'] = {filename:hashlib.sha256((args.moneypuck_dir/filename).read_bytes()).hexdigest()
                                   for filename in ['skaters.csv','goalies.csv']} if args.moneypuck_dir else {}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(dump_json(board))
        if args.csv:
            export_csv(board,args.csv)
        available=sum(p['projected_points'] is not None for p in board['players'])
        print(f"Built {available} baseline projections and {len(board['players'])-available} unranked players: {args.output}")
        print('Historical-rate baseline. Review workload, injuries and Yahoo eligibility before using it to draft.')
        return 0
    if args.action=='init':
        draft.initialize(args.db,args.board,args.teams,args.slot)
        print(f'Created {args.teams}-team local draft: {args.db}')
    elif args.action=='pick':
        print(dump_json(draft.pick_player(args.db,args.player)))
    elif args.action=='undo':
        print(dump_json(draft.undo(args.db)))
    elif args.action=='set-slot':
        draft.set_slot(args.db,args.slot)
        print(f'Your draft slot is {args.slot}.')
    elif args.action=='positions':
        draft.set_positions(args.db,args.player,[p.strip() for p in args.eligible.split(',')],args.note)
        print('Updated local eligibility; evidence note saved.')
    elif args.action=='export':
        if args.db.resolve()==args.output.resolve():
            raise ValueError('Export cannot overwrite the draft database')
        draft.export_draft(args.db,args.output)
        print(f'Exported draft and audit log: {args.output}')
    elif args.action=='board':
        if args.limit < 1:
            raise ValueError('limit must be positive')
        board=draft.draft_board(args.db,args.search,args.position,args.limit)
        if args.json:
            print(dump_json(board)); return 0
        print(f"{board['model']} | {board['teams']} teams | Pick {board['pick']} | On clock: {board['on_clock']}")
        print(f"Your slot: {board['slot']} | Your next pick: {board['your_next_pick']} | Players remaining: {board['remaining_count']}")
        print('PROVISIONAL: historical carry-forward; Yahoo eligibility and role/injury adjustments need review.')
        print(f"{'ID':14} {'Player':25} {'Team':5} {'Pos':8} {'GP':>6} {'FP/GP':>7} {'FP':>8} {'Fits':5}")
        for p in board['candidates']:
            values=['--' if p[k] is None else f"{number(p[k],k):.1f}" for k in ['projected_games','points_per_game','projected_points']]
            print(f"{p['id']:14} {p['name'][:25]:25} {str(p['team']):5} {'/'.join(p['positions']):8} {values[0]:>6} {values[1]:>7} {values[2]:>8} {str(p['fits_roster']):5}")
        print('Sorted by baseline season points among players who fit, not a full draft optimizer. Use --json for evidence and flags.')
        if board['roster']:
            print('Your roster: '+', '.join(f"{p['name']} ({board['assignment'].get(p['id'],'unassigned')})" for p in board['roster']))
    return 0
