"""Parse NHL's explicitly downloadable 2026-27 schedule, pdftotext -layout output.

Official published document, not a supported developer API. Times are omitted:
this adapter preserves published game dates, not inferred UTC timestamps.
"""
from collections import Counter, defaultdict
from datetime import date
import re

TEAMS = dict(zip(
    ['Anaheim Ducks','Boston Bruins','Buffalo Sabres','Calgary Flames','Carolina Hurricanes',
     'Chicago Blackhawks','Colorado Avalanche','Columbus Blue Jackets','Dallas Stars',
     'Detroit Red Wings','Edmonton Oilers','Florida Panthers','Los Angeles Kings',
     'Minnesota Wild','Montreal Canadiens','Nashville Predators','New Jersey Devils',
     'New York Islanders','New York Rangers','Ottawa Senators','Philadelphia Flyers',
     'Pittsburgh Penguins','San Jose Sharks','Seattle Kraken','St. Louis Blues',
     'Tampa Bay Lightning','Toronto Maple Leafs','Utah Mammoth','Vancouver Canucks',
     'Vegas Golden Knights','Washington Capitals','Winnipeg Jets'],
    'ANA BOS BUF CGY CAR CHI COL CBJ DAL DET EDM FLA LAK MIN MTL NSH NJD NYI NYR OTT PHI PIT SJS SEA STL TBL TOR UTA VAN VGK WSH WPG'.split()))
OPPONENTS = dict(zip(
    ['Anaheim','Boston','Buffalo','Calgary','Carolina','Chicago','Colorado','Columbus',
     'Dallas','Detroit','Edmonton','Florida','Los Angeles','Minnesota','Montreal',
     'Nashville','New Jersey','N.Y. Islanders','N.Y. Rangers','Ottawa','Philadelphia',
     'Pittsburgh','San Jose','Seattle','St. Louis','Tampa Bay','Toronto','Utah',
     'Vancouver','Vegas','Washington','Winnipeg'], TEAMS.values()))
MONTHS = {'Sep':9,'Oct':10,'Nov':11,'Dec':12,'Jan':1,'Feb':2,'Mar':3,'Apr':4}
ROW = re.compile(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.\s+(\w{3})\s+(\d+)\s+\d+:\d+\s+[AP]M\s+(.+?)\s*$')


def parse_schedule(text: str) -> dict:
    observations = defaultdict(list)
    pages = set()
    for page in text.split('\f'):
        header = re.search(r'2026-27 Schedule for the (.+)', page)
        if not header:
            continue
        name = header.group(1).strip().replace('N.Y.', 'New York')
        team = TEAMS[name]
        if team in pages:
            raise ValueError('Duplicate team schedule')
        pages.add(team)
        for line in page.splitlines():
            starts = list(re.finditer(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.\s+', line))
            for i, start in enumerate(starts):
                part = line[start.start():starts[i+1].start() if i+1 < len(starts) else len(line)]
                match = ROW.fullmatch(part.strip())
                if not match:
                    raise ValueError(f'Unrecognized schedule row: {part}')
                weekday, month, day, opponent = match.groups()
                month = MONTHS[month]
                when = date(2026 if month >= 9 else 2027, month, int(day))
                if when.strftime('%a') != weekday:
                    raise ValueError('Date/weekday mismatch')
                away = opponent.startswith('AT ')
                other = OPPONENTS[opponent.removeprefix('AT ').strip()]
                home, visitor = (other, team) if away else (team, other)
                observations[(when.isoformat(), home, visitor)].append(team)
    if pages != set(TEAMS.values()):
        raise ValueError('Missing team schedules')
    counts = Counter(); dates = set(); games = {}
    for (day, home, away), owners in sorted(observations.items()):
        if sorted(owners) != sorted([home, away]) or home == away:
            raise ValueError(f'Team schedules disagree: {day} {home} {away}: {owners}')
        for team in (home, away):
            if (day, team) in dates:
                raise ValueError('Team scheduled twice on same date')
            dates.add((day, team)); counts[team] += 1
        # Document has no NHL game IDs. Never mislabel our composite key.
        games[f'nhl-pdf:{day}:{away}:{home}'] = {'date':day,'teams':[away,home], 'home':home,'away':away}
    if len(games) != 1344 or set(counts.values()) != {84}:
        raise ValueError('Incomplete 84-game season')
    return {'season':'20262027','games':games,'team_games':dict(counts),
            'source_kind':'official_published_document', 'schedule_vintage':'2026-07-15',
            'date_basis':'NHL published game date; Yahoo matchup boundaries unverified'}


def normalize_club_schedules(snapshots: dict) -> dict:
    """Require reciprocal team observations and a complete regular season."""
    games = {}; seen = defaultdict(set)
    for club, snapshot in snapshots.items():
        for row in snapshot['payload']['games']:
            if row['gameType'] != 2:
                continue
            if row['season'] != 20262027:
                raise ValueError('Wrong schedule season')
            home = row['homeTeam']['abbrev']; away = row['awayTeam']['abbrev']
            if club not in (home, away):
                raise ValueError('Club response contains unrelated game')
            when = date.fromisoformat(row['gameDate'])
            game = {'date':when.isoformat(),'teams':[away,home],'home':home,'away':away,
                    'start':row['startTimeUTC']}
            key = str(row['id'])
            if key in games and games[key] != game:
                raise ValueError('Conflicting club schedule observations')
            if club in seen[key]:raise ValueError('Duplicate club game')
            games[key] = game; seen[key].add(club)
    counts = Counter(); dates = set()
    for key, game in games.items():
        if seen[key] != set(game['teams']):raise ValueError('Missing reciprocal club observation')
        for team in game['teams']:
            if (team, game['date']) in dates:raise ValueError('Team plays twice on same date')
            dates.add((team,game['date']));counts[team]+=1
    if set(counts) != set(TEAMS.values()) or set(counts.values()) != {84} or len(games) != 1344:
        raise ValueError('Incomplete 32-team, 84-game regular season')
    return {'season':'20262027','games':dict(sorted(games.items())), 'team_games':dict(counts),
            'source_kind':'undocumented_public_endpoint', 'date_basis':'NHL gameDate, not verified Yahoo matchup dates',
            'sources':[{k:s[k] for k in ('source','retrieved_at','sha256')} for s in snapshots.values()]}
