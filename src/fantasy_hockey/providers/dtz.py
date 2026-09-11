"""Read cached values from a permitted DtZ XLSX export, never execute formulas.

Only the two visible projection tables are read. Provider ranks, fantasy scores,
ADP and eligibility are deliberately excluded from the projection adapter.
"""
from datetime import date
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ..board import normalized_name
from ..market import TEAM_ALIASES
from ..scoring import number, score

SOURCE = 'https://docs.google.com/spreadsheets/d/1hlwGkHQiC9PNg1bs5jHRK-pgyaI9QMbVRe0pMhOVuqU/edit'
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
FIELDS = {
    'skater': {'goals':'Goals', 'assists':'Assists', 'plus_minus':'+/-',
               'power_play_points':'PP Points', 'shots_on_goal':'SOG', 'hits':'Hit', 'blocks':'BLK'},
    'goalie': {'wins':'W', 'goals_against':'GA', 'saves':'SV', 'shutouts':'SO'},
}


def table_rows(path: Path, sheet_name: str) -> list[dict]:
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in row.findall('.//m:t', NS))
                       for row in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = {s.attrib['name']:s for s in workbook.find('m:sheets',NS)}
        if sheet_name not in sheets or sheets[sheet_name].get('state','visible') != 'visible':
            raise ValueError('Missing visible projection table: '+sheet_name)
        relationships = {r.attrib['Id']:r.attrib for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        relation = relationships[sheets[sheet_name].attrib[RID]]
        if relation.get('TargetMode') == 'External':raise ValueError('External worksheet is unsupported')
        target = relation['Target']
        member = target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl')/target)
        rows = []
        for row in ET.fromstring(archive.read(member)).findall('m:sheetData/m:row',NS):
            values = {}
            for cell in row:
                col = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                value = cell.find('m:v',NS)
                text = value.text if value is not None else None
                if cell.get('t') == 's':text = strings[int(text)]
                elif cell.get('t') == 'inlineStr':text = ''.join(t.text or '' for t in cell.findall('.//m:t',NS))
                elif cell.get('t') == 'e':text = None
                values[col] = text
            rows.append(values)
    if not rows:raise ValueError('Empty projection table')
    headers = {col:name for col,name in rows[0].items() if name}
    if len(set(headers.values())) != len(headers):raise ValueError('Duplicate projection headers')
    return [{headers[col]:value for col,value in row.items() if col in headers} for row in rows[1:]]


def projection_dossier(path: Path, board: dict, as_of: date, source: str = SOURCE) -> tuple[list[dict], dict]:
    """Require unique name/kind/team identity; record conflicting provider IDs.

    The published goalie ID column can be misaligned. Never join on it alone.
    Our previously reconciled registry supplies IDs for exact unique matches.
    """
    known = {p['id']:p for p in board['players']}
    accepted = []; rejected = []; corrections = []; outside = 0; seen = set()
    for kind, sheet in (('skater','Skater Projections'),('goalie','Goalie Projections')):
        for row in table_rows(path,sheet):
            if not row.get('Player'):continue
            pid = None
            try:
                raw_id = number(row.get('PlayerId' if kind == 'skater' else 'playerId'),'NHL ID')
                if raw_id <= 0 or raw_id != int(raw_id):raise ValueError('Invalid NHL ID')
                source_id = 'nhl:'+str(int(raw_id))
                matches = [p for p in known.values() if normalized_name(p['name']) == normalized_name(row['Player'])
                           and p['kind'] == kind
                           and TEAM_ALIASES.get(p['team'],p['team']) == TEAM_ALIASES.get(row.get('Team'),row.get('Team'))]
                if len(matches) != 1:
                    if len(matches)>1:raise ValueError('Ambiguous name/kind/team identity')
                    if source_id in known:
                        pid = source_id
                        raise ValueError('Identity or team differs from reviewed registry')
                    outside += 1;continue
                pid = matches[0]['id']
                if source_id != pid:
                    corrections.append({'name':row['Player'],'source_id':source_id,'resolved_id':pid,
                                        'basis':'Unique exact normalized name, kind and team in reconciled NHL registry'})
                if pid in seen:raise ValueError('Duplicate projection NHL ID')
                seen.add(pid)
                if pid not in known:outside += 1;continue
                player = known[pid]
                if normalized_name(row['Player']) != normalized_name(player['name']) or kind != player['kind']:
                    raise ValueError('Identity or kind conflict')
                if TEAM_ALIASES.get(row.get('Team'),row.get('Team')) != TEAM_ALIASES.get(player['team'],player['team']):
                    raise ValueError('Projection team differs from reviewed team')
                games = number(row.get('GP'),'GP')
                if not 0 < games <= number(board['assumptions']['season_games'],'season games'):
                    raise ValueError('GP outside season bounds')
                stats = {stat:number(row.get(label),label) for stat,label in FIELDS[kind].items()
                         if number(board['scoring'][kind].get(stat,0),'weight') != 0}
                score(kind,stats,board['scoring'][kind])
                if kind == 'goalie':
                    if any(stats.get(k,0)>games for k in ('wins','shutouts')):raise ValueError('Outcomes exceed GP')
                    if abs(number(row.get('SA'),'SA')-stats['saves']-stats['goals_against']) > 1:
                        raise ValueError('Shots against do not reconcile with saves and GA')
                elif stats['power_play_points'] > stats['goals']+stats['assists']:
                    raise ValueError('PPP exceeds points')
                accepted.append({'id':pid,'season':board['season'],'as_of':as_of.isoformat(),
                                 'source':source,'basis':'season_total','games':games,'stats':stats,
                                 'provider':'DtZ free preseason projections',
                                 'source_player_id':source_id,
                                 'identity_resolution':'Unique name/kind/team match to reconciled NHL registry',
                                 'note':'Cached published totals, rescored for this league. Unvalidated forecast, not historical results.'})
            except ValueError as exc:
                rejected.append({'id':pid,'name':row['Player'],'reason':str(exc)})
    # A duplicate invalidates every occurrence rather than silently choosing the first.
    bad_ids = {r['id'] for r in rejected if r['reason'] == 'Duplicate projection NHL ID'}
    accepted = [r for r in accepted if r['id'] not in bad_ids]
    return accepted, {'accepted':len(accepted),'outside_board':outside,'rejected':rejected,
                      'identity_corrections':corrections,
                      'missing_board_ids':sorted(set(known)-{r['id'] for r in accepted}),
                      'source':source,'as_of':as_of.isoformat(),
                      'interpretation':'Snapshot receipt date, not an assertion of original publication date. No workbook code executed.'}
