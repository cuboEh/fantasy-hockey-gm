"""Dated market exports; rankings and ADP never alter projected production."""
import csv
from datetime import date
from pathlib import Path
from .scoring import number


def load_market(path: Path, season: str, draft_date: date):
    result={}
    with path.open(newline='') as stream:
        for row in csv.DictReader(stream):
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
