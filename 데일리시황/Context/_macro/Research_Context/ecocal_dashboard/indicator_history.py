"""Keep reported WECO rows after they leave the rolling source calendar."""
from __future__ import annotations

import json
from pathlib import Path

HISTORY_FILE = Path(__file__).with_name('indicator_history.json')


def _stored(event):
    """Historical rows retain the source facts and verified commentary, not search leads."""
    row = json.loads(json.dumps(event, ensure_ascii=False))
    row['record_origin'] = 'history'
    for house in row.get('houses', []):
        house['search_candidates'] = []
        house['bases'] = []
        if house.get('status') in {'candidate', 'basis'} and not (house.get('direct') or house.get('forecasts') or house.get('commentary')):
            house['status'] = 'uncovered'
            house['gap'] = '과거 후보 검색은 이력에 보존하지 않았다. 신규 지표별 검토가 필요하다.'
    return row


def read(path=HISTORY_FILE):
    if not path.exists():
        return {}
    bundle = json.loads(path.read_text(encoding='utf-8'))
    if bundle.get('schema_version') != 1:
        raise ValueError('지원하지 않는 누적 지표 이력 형식')
    rows = bundle['events']
    if len({e['id'] for e in rows}) != len(rows):
        raise ValueError('누적 지표 ID 중복')
    return {e['id']: e for e in rows}


def merge(current, history):
    """Fresh source rows win. Only past reported rows are carried forward."""
    seen = {e['id'] for e in current}
    archived = [_stored(e) for eid, e in history.items()
                if eid not in seen and e.get('actual') is not None]
    for e in current:
        e['record_origin'] = 'current'
    rows = current + archived
    rows.sort(key=lambda e: (e['date'], e['time'], e['country_code'], e['event'], e['period']))
    return rows


def updated(history, current):
    rows = dict(history)
    rows.update((e['id'], _stored(e)) for e in current if e.get('actual') is not None)
    return {'schema_version': 1, 'events': sorted(rows.values(),
            key=lambda e: (e['date'], e['time'], e['country_code'], e['event'], e['period']))}
