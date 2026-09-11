"""Dated pre-season context labels, stored separately from outcome observations."""
from datetime import date

FIELDS={'case_id','player_id','season','cutoff','event_type','event_date','source_date',
        'source','fact','team_before','team_after','expected_role','role_label_kind',
        'health_status','projected_starts','selection_note'}


def validate_cases(cases):
    seen=set()
    for case in cases:
        if set(case)!=FIELDS:raise ValueError('Case fields must match the pre-season-only schema')
        if case['case_id'] in seen:raise ValueError('Duplicate case ID')
        seen.add(case['case_id'])
        cutoff=date.fromisoformat(case['cutoff'])
        if max(date.fromisoformat(case['event_date']),date.fromisoformat(case['source_date']))>cutoff:
            raise ValueError('Evidence is after decision cutoff')
        year=int(case['season'][:4])
        if case['season']!=f'{year}{year+1}' or cutoff.year!=year:
            raise ValueError('Invalid season/cutoff year')
        if not case['source'] or not case['fact'] or not case['selection_note']:
            raise ValueError('Source, factual note and selection caveat required')
        if not case['player_id'].startswith('nhl:') or not case['player_id'][4:].isdigit():
            raise ValueError('Verified NHL identity required')
        if case['event_type'] not in {'trade','signing','role_expectation','injury_return'}:
            raise ValueError('Unsupported context event')
        if case['role_label_kind'] not in {'unknown','editorial_expectation','coach_statement'}:
            raise ValueError('Expected role must identify evidence type')
        if case['role_label_kind']=='unknown' and case['expected_role'] is not None:
            raise ValueError('Unknown role cannot carry an assigned role')
        if case['projected_starts'] is not None:
            raise ValueError('Pilot requires numeric start projections to remain unknown')
    return cases
