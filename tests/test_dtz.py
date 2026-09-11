from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from fantasy_hockey.providers.dtz import projection_dossier, table_rows


class DtzTests(unittest.TestCase):
    def setUp(self):
        self.board={'season':'2026-27','assumptions':{'season_games':84},
                    'scoring':{'goalie':{'wins':5,'goals_against':-3,'saves':Decimal('.6'),'shutouts':5}},
                    'players':[{'id':'nhl:1','name':'Example Goalie','kind':'goalie','team':'TBL'}]}
        self.row={'Player':'Example Goalie','playerId':'1.0','Team':'TB','GP':'50',
                  'W':'30','GA':'120','SV':'1300','SA':'1420','SO':'3'}

    def run_rows(self,rows):
        with patch('fantasy_hockey.providers.dtz.table_rows',side_effect=[[],rows]):
            return projection_dossier(Path('unused.xlsx'),self.board,date(2026,9,11))

    def test_corrected_id_requires_exact_unique_identity_and_scores_raw_stats(self):
        self.row['playerId']='99'
        projections,report=self.run_rows([self.row])
        self.assertEqual(projections[0]['id'],'nhl:1')
        self.assertEqual(projections[0]['stats']['saves'],1300)
        self.assertEqual(report['identity_corrections'][0]['source_id'],'nhl:99')
        self.row['Team']='EDM'
        self.assertEqual(self.run_rows([self.row])[0],[])

    def test_duplicate_ambiguous_and_incomplete_records_are_quarantined(self):
        self.assertEqual(self.run_rows([self.row,self.row])[0],[])
        self.board['players'].append({**self.board['players'][0],'id':'nhl:2'})
        self.assertEqual(self.run_rows([self.row])[0],[])
        self.board['players'].pop()
        self.row['SV']=None
        self.assertEqual(self.run_rows([self.row])[0],[])

    def test_impossible_goalie_line_is_rejected(self):
        self.row['W']='60'
        self.assertEqual(self.run_rows([self.row])[0],[])

    def test_unmatched_row_cannot_quarantine_another_players_correct_projection(self):
        other={**self.row,'Player':'Unrelated Goalie','Team':'EDM'}
        projections,_=self.run_rows([self.row,other])
        self.assertEqual([p['id'] for p in projections],['nhl:1'])
        self.row['W']='30';self.row['SA']='900'
        self.assertEqual(self.run_rows([self.row])[0],[])

    def test_xlsx_reads_cached_values_without_executing_formula(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.xlsx'
            with ZipFile(path,'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Goalie Projections" r:id="r1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet7.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet7.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>GP</t></is></c></row><row><c r="A2"><f>UNSUPPORTED_FUNCTION()</f><v>50</v></c></row><row><c r="A3" t="e"><v>#REF!</v></c></row></sheetData></worksheet>')
            self.assertEqual(table_rows(path,'Goalie Projections'),[{'GP':'50'},{'GP':None}])
