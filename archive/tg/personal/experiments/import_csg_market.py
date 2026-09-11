"""Read cached market cells from a shared CSG workbook. Never executes macros.

The source's Yahoo ADP column is preserved as labeled, not independently verified.
Matches use NHL IDs from unambiguous historical abbreviated names. Ambiguities
remain unmatched. The publication date is a provenance claim, not proof of an
immutable archive. Inputs remain private.
"""
import argparse
import csv
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as E
import zipfile
from fantasy_hockey.board import normalized_name


def abbreviation(name):
    pieces=name.split()
    return normalized_name(pieces[0][0]+' '+ ' '.join(pieces[1:])) if len(pieces)>1 else ''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook',type=Path,required=True);p.add_argument('--history',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();n={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    crosswalk=defaultdict(set)
    for file in a.history:
        for row in json.loads(file.read_text())['records']:crosswalk[abbreviation(row['name'])].add(row['id'])
    with zipfile.ZipFile(a.workbook) as z:
        strings=[''.join(s.itertext()) for s in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',n)]
        rows=[]
        for row in E.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row',n):
            cells={}
            for c in row.findall('m:c',n):
                value=c.find('m:v',n)
                if value is not None:
                    cells[''.join(x for x in c.get('r') if x.isalpha())]=strings[int(value.text)] if c.get('t')=='s' else value.text
            rows.append(cells)
    if not any(r.get('R')=='Yahoo ADP' and r.get('E')=='Player' for r in rows):raise ValueError('Workbook layout changed')
    imported=[];unmatched=[];seen=set()
    for row in rows:
        if not row.get('E') or not row.get('R'):continue
        try:value=float(row['R'])
        except ValueError:continue
        if value<=0:continue
        ids=crosswalk[abbreviation(row['E'])]
        if len(ids)!=1:
            unmatched.append({'name':row['E'],'candidate_ids':sorted(ids)});continue
        identity=next(iter(ids))
        if identity in seen:raise ValueError('Duplicate mapped market identity')
        seen.add(identity)
        imported.append({'id':identity,'season':'20242025','as_of':'2024-09-26',
                         'source':'CSG 2024 shared workbook; Yahoo ADP column, author cites FantasyPros',
                         'metric':'adp','value':value,'name':row['E']})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','season','as_of','source','metric','value','name']);w.writeheader();w.writerows(imported)
    a.output.with_suffix('.metadata.json').write_text(json.dumps({'matched':len(imported),'unmatched':unmatched,
        'workbook_sha256':hashlib.sha256(a.workbook.read_bytes()).hexdigest(),
        'history_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.history},
        'source_post':'https://www.reddit.com/r/fantasyhockey/comments/1fpy57m/',
        'warnings':['Publication date and cached workbook date support historical use but are not immutable archive proof',
                    'Position columns not imported; displayed platform selection may differ from Yahoo']},indent=2))
    print(len(imported),'matched;',len(unmatched),'unmatched')


if __name__=='__main__':main()
