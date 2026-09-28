"""Register verified BofA originals and audit the bounded five-house browser run."""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]
COLLECTOR = BASE / '.collector'
sys.path.insert(0,str(BASE))
from macro_bulk_downloader import Report, State, is_pdf

state = State(COLLECTOR)
bofa = json.loads((COLLECTOR / 'manual_bofa_20260907_manifest.json').read_text(encoding='utf-8'))
bofa_catalog = {r['id']:r for r in csv.DictReader((COLLECTOR / 'manual_bofa_20260907.tsv').open(encoding='utf-8'), delimiter='\t')}
assert len(bofa) == len(bofa_catalog) == 26
for item in bofa:
    item['regions'] = bofa_catalog[item['id']]['regions']
    path = Path(item['saved_path'])
    raw = path.read_bytes()
    assert is_pdf(raw) and hashlib.sha256(raw).hexdigest()==item['sha256']
    report = Report('BofA',item['id'],item['title'],item['publication_date'],item['source_list'],item['source_list'],region=item['regions'],published=item['publication_date'])
    state.record(report)
    if not state.downloaded(report):
        state.result(report,'downloaded',path=path,raw=raw)
(COLLECTOR / 'manual_bofa_20260907_manifest.json').write_text(json.dumps(bofa,ensure_ascii=False,indent=2),encoding='utf-8')

keys = set()
for name in ['browser_gs_20260901_20260907.json','browser_hsbc_verified_20260901_20260907.json','browser_citi_20260901_20260907.json']:
    keys.update((r['house'],r['doc_id']) for r in json.loads((COLLECTOR / name).read_text(encoding='utf-8')))
keys.update(('BofA',r['id']) for r in bofa)
keys.update(('JPM',r['id']) for r in csv.DictReader((COLLECTOR / 'manual_jpm_20260907_manifest.csv').open(encoding='utf-8-sig')))
assert len(keys)==316, len(keys)
records=[]
errors=[]
hashes=defaultdict(list)
for house,doc_id in sorted(keys):
    row=state.db.execute('SELECT * FROM reports WHERE house=? AND doc_id=?',(house,doc_id)).fetchone()
    if not row:
        errors.append(f'Missing state: {house}/{doc_id}')
        continue
    record=dict(row)
    if record['status']=='downloaded':
        try:
            path=Path(record['path']).resolve(strict=True)
            assert path.is_relative_to((BASE/'outdated'/house).resolve())
            raw=path.read_bytes()
            assert is_pdf(raw)
            assert len(raw)==record['bytes']
            assert hashlib.sha256(raw).hexdigest()==record['sha256']
            reader=PdfReader(path)
            assert len(reader.pages)>0
            for page in reader.pages:
                stream=page.get_contents()
                if stream is not None:
                    stream.get_data()
            record['verified_pages']=len(reader.pages)
            hashes[(house,record['sha256'])].append(doc_id)
        except Exception as exc:
            errors.append(f'{house}/{doc_id}: {exc}')
    records.append(record)
state.export()
state.db.close()
summary={house:dict(Counter(r['status'] for r in records if r['house']==house)) for house in ['HSBC','GS','JPM','Citi','BofA']}
downloaded=[r for r in records if r['status']=='downloaded']
duplicate_content=[{'house':h,'doc_ids':ids} for (h,_),ids in hashes.items() if len(ids)>1]
known_paths={str(Path(r['path']).resolve()) for r in downloaded}
untracked_files=[str(p) for h in summary for p in (BASE/'outdated'/h).glob('*.pdf') if str(p.resolve()) not in known_paths]
audit=dict(period={'start':'2026-09-01','end':'2026-09-07','date_basis':'Observed site list dates; GS/Citi list dates can differ from source PDF timezone dates.'},method='Existing logged-in Chrome via browser extension; original downloads copied byte-for-byte. Not the standalone Python collector.',backfill_9_months_complete=False,observed_candidates=len(keys),downloaded=len(downloaded),bytes=sum(r['bytes'] for r in downloaded),pages=sum(r['verified_pages'] for r in downloaded),by_house=summary,verification_errors=errors,duplicate_content=duplicate_content,untracked_files=untracked_files,records=records)
(COLLECTOR/'browser_run_20260901_20260907_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k!='records'},ensure_ascii=False))
if errors:
    raise SystemExit(2)
