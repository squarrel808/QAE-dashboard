"""Quarantine three copies made by this browser run's overly broad title match."""
import hashlib
import json
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from macro_bulk_downloader import Report, State

state=State(BASE/'.collector')
repairs=[]
# The copied bytes were verified to belong to these other reports.
pairs={'HJzdRjkCxjQZ':'CkgWjwqCxjQZ','MCdvQ7NCxjQZ':'bDmTTMTCxjQZ','nwH6HzVCxjQZ':'bDmTTMTCxjQZ'}
quarantine=BASE/'.collector/rejected_title_matches'
quarantine.mkdir(exist_ok=True)
for wrong_id,actual_id in pairs.items():
    row=state.db.execute('SELECT * FROM reports WHERE house=? AND doc_id=?',('HSBC',wrong_id)).fetchone()
    actual=state.db.execute('SELECT * FROM reports WHERE house=? AND doc_id=?',('HSBC',actual_id)).fetchone()
    if row['status']=='pending_title_repair':
        continue
    source=Path(row['path']).resolve(strict=True)
    assert source.parent==(BASE/'outdated/HSBC').resolve()
    raw=source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==row['sha256']==actual['sha256']
    target=quarantine/source.name
    assert not target.exists()
    source.rename(target)
    report=Report('HSBC',wrong_id,row['title'],row['published'],row['url'],row['source_url'],published=row['published'])
    state.result(report,'pending_title_repair',error='Incorrect generated copy quarantined; original download pending. Source PDF actually belongs to '+actual_id)
    repairs.append(dict(doc_id=wrong_id,actual_doc_id=actual_id,quarantined_path=str(target),sha256=row['sha256']))
state.export()
state.db.close()
if repairs:
    (BASE/'.collector/title_match_repairs_20260907.json').write_text(json.dumps(repairs,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(repairs,ensure_ascii=False))
