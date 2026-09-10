"""Persistent manual snake draft tracking, with no connection to Yahoo."""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from .board import dump_json, read_json
from .scoring import number


@contextmanager
def connect(path: Path):
    if not path.is_file():
        raise ValueError("Draft database does not exist; initialize it first")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def snake_team(pick: int, teams: int) -> int:
    if pick < 1 or teams < 2:
        raise ValueError("Invalid pick or league size")
    round_index, position = divmod(pick - 1, teams)
    return position + 1 if round_index % 2 == 0 else teams - position


def initialize(path: Path, board_path: Path, teams: int, slot: int | None) -> None:
    if not 2 <= teams <= 32 or (slot is not None and not 1 <= slot <= teams):
        raise ValueError("Invalid team count or draft slot")
    board = read_json(board_path)
    if board.get("schema_version") != 1 or not isinstance(board.get("players"), list):
        raise ValueError("Unsupported draft board")
    if len({p['id'] for p in board['players']}) != len(board['players']):
        raise ValueError("Duplicate player IDs")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass  # Never overwrite existing draft progress.
    try:
        with connect(path) as db:
            db.executescript('''
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE players (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE picks (pick INTEGER PRIMARY KEY, team INTEGER NOT NULL,
                    player_id TEXT NOT NULL UNIQUE REFERENCES players(id));
                CREATE TABLE events (id INTEGER PRIMARY KEY, at TEXT NOT NULL,
                    action TEXT NOT NULL, payload TEXT NOT NULL);
            ''')
            settings = {"teams": teams, "slot": slot, "board": {k:v for k,v in board.items() if k != "players"}}
            db.executemany("INSERT INTO metadata VALUES (?, ?)", [(k,dump_json(v)) for k,v in settings.items()])
            db.executemany("INSERT INTO players VALUES (?, ?)", [(p['id'],dump_json(p)) for p in board['players']])
    except Exception:
        path.unlink()  # Only remove the empty/new database created by this call.
        raise


def settings(db) -> dict:
    return {r["key"]:json.loads(r["value"]) for r in db.execute("SELECT * FROM metadata")}


def log(db, action: str, payload: dict) -> None:
    db.execute("INSERT INTO events(at, action, payload) VALUES (?, ?, ?)",
               (datetime.now(timezone.utc).isoformat(), action, dump_json(payload)))


def resolve(db, query: str) -> dict:
    rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM players")]
    exact = [p for p in rows if p['id'] == query or p['name'].casefold() == query.casefold()]
    if len(exact) == 1:
        return exact[0]
    matches = exact or [p for p in rows if query.casefold() in p['name'].casefold()]
    if len(matches) != 1:
        raise ValueError("Player query must match one player: " + ", ".join(p['name'] for p in matches[:8]))
    return matches[0]


def pick_player(path: Path, query: str) -> dict:
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        info = settings(db)
        next_pick = db.execute("SELECT COUNT(*) + 1 FROM picks").fetchone()[0]
        rounds = sum(v for k,v in info['board']['roster_slots'].items() if k not in {'IR','IR+'})
        if next_pick > rounds * info['teams']:
            raise ValueError("Draft is complete")
        player = resolve(db, query)
        if db.execute("SELECT 1 FROM picks WHERE player_id=?", (player['id'],)).fetchone():
            raise ValueError("Player has already been drafted")
        team = snake_team(next_pick, info['teams'])
        db.execute("INSERT INTO picks VALUES (?, ?, ?)", (next_pick, team, player['id']))
        result = {"pick":next_pick,"team":team,"id":player['id'],"name":player['name']}
        log(db, "pick", result)
        return result


def undo(path: Path) -> dict:
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM picks ORDER BY pick DESC LIMIT 1").fetchone()
        if row is None:
            raise ValueError("No pick to undo")
        result = dict(row)
        db.execute("DELETE FROM picks WHERE pick=?", (row['pick'],))
        log(db,"undo",result)
        return result


def set_slot(path: Path, slot: int) -> None:
    with connect(path) as db:
        if not 1 <= slot <= settings(db)['teams']:
            raise ValueError("Draft slot is outside this league")
        db.execute("UPDATE metadata SET value=? WHERE key='slot'", (str(slot),))
        log(db,"set_slot",{"slot":slot})


def set_positions(path: Path, query: str, positions: list[str], note: str) -> None:
    if not positions or len(set(positions)) != len(positions) or any(p not in {'C','LW','RW','D','G'} for p in positions) or not note.strip():
        raise ValueError("Provide valid unique positions and an evidence note")
    with connect(path) as db:
        player = resolve(db, query)
        if (player['kind']=='goalie' and positions != ['G']) or (player['kind']=='skater' and 'G' in positions):
            raise ValueError("Eligibility conflicts with player type")
        before = player['positions']
        player['positions'] = positions
        player['position_source'] = f"User supplied: {note}"
        player['flags'] = [f for f in player['flags'] if f != 'eligibility_unverified']
        db.execute("UPDATE players SET payload=? WHERE id=?", (dump_json(player), player['id']))
        log(db,"set_positions",{"id":player['id'],"before":before,"after":positions,"note":note})


def roster_assignment(players: list[dict], slots: dict[str,int]) -> dict[str,str]:
    """Maximum matching, with bench after active slots and no injury slots."""
    expanded = [(pos,index) for pos,count in slots.items() if pos not in {'IR','IR+'}
                for index in range(count)]
    expanded.sort(key=lambda s:(s[0]=='BN',s))
    assigned = {}
    def place(player_index: int, visited: set) -> bool:
        for slot in expanded:
            if slot in visited or (slot[0] != 'BN' and slot[0] not in players[player_index]['positions']):
                continue
            visited.add(slot)
            if slot not in assigned or place(assigned[slot],visited):
                assigned[slot] = player_index
                return True
        return False
    for index in range(len(players)):
        place(index,set())
    return {players[index]['id']:f"{slot[0]}{slot[1]+1}" for slot,index in assigned.items()}


def draft_board(path: Path, search: str = "", position: str | None = None, limit: int = 20) -> dict:
    with connect(path) as db:
        info = settings(db)
        picks = [dict(r) for r in db.execute("SELECT * FROM picks ORDER BY pick")]
        players = [json.loads(r[0]) for r in db.execute("SELECT payload FROM players")]
    selected = {p['player_id'] for p in picks}
    own_ids = {p['player_id'] for p in picks if p['team']==info['slot']}
    own = [p for p in players if p['id'] in own_ids]
    slots = info['board']['roster_slots']
    assignment = roster_assignment(own,slots)
    candidates = []
    for player in players:
        if player['id'] in selected or search.casefold() not in player['name'].casefold():
            continue
        if position and position not in player['positions']:
            continue
        row = dict(player)
        row['fits_roster'] = None if info['slot'] is None else len(roster_assignment(own+[player],slots)) == len(own)+1
        candidates.append(row)
    candidates.sort(key=lambda p:(p['fits_roster'] is False,p['projected_points'] is None,
                                  -number(p['projected_points'] or 0,'points'),p['id']))
    next_pick = len(picks)+1
    total_picks = info['teams'] * sum(v for k,v in slots.items() if k not in {'IR','IR+'})
    own_next = next((i for i in range(next_pick,total_picks+1) if snake_team(i,info['teams'])==info['slot']),None)
    return {"teams":info['teams'],"slot":info['slot'],"pick":next_pick if next_pick<=total_picks else None,
            "on_clock":snake_team(next_pick,info['teams']) if next_pick<=total_picks else None,
            "your_next_pick":own_next,"picks_until_yours":own_next-next_pick if own_next else None,
            "model":info['board']['model'],"warnings":info['board']['warnings'],
            "roster":own,"assignment":assignment,"unassigned_roster_ids":sorted(own_ids-set(assignment)),
            "remaining_count":len(players)-len(selected),"candidates":candidates[:limit]}


def export_draft(path: Path, destination: Path) -> None:
    with connect(path) as db:
        payload = {"settings":settings(db),
                   "players":[json.loads(r[0]) for r in db.execute('SELECT payload FROM players ORDER BY id')],
                   "picks":[dict(r) for r in db.execute('SELECT * FROM picks ORDER BY pick')],
                   "events":[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id')]}
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(dump_json(payload))
