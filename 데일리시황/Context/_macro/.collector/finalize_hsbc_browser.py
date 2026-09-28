"""Verify and reconcile original HSBC PDFs without rewriting their contents."""
import csv
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from macro_bulk_downloader import Report, State, is_pdf, safe_filename

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value or '').casefold() if c.isalnum())

catalog = list(csv.DictReader((BASE / '.collector/browser_hsbc_20260901_20260907.csv').open(encoding='utf-8-sig', newline='')))
non_pdf_ids = set(json.loads((BASE / '.collector/hsbc_non_pdf_20260907.json').read_text(encoding='utf-8')))
files = []
for source in Path(r'C:\Users\infomax\Downloads').iterdir():
    if not source.is_file() or source.suffix.lower() not in ('.pdf','.tmp') or source.stat().st_mtime < datetime(2026,9,7).timestamp():
        continue
    if source.suffix.lower() == '.pdf' and not source.stem.isdigit():
        continue
    raw = source.read_bytes()
    if not is_pdf(raw):
        continue
    try:
        reader = PdfReader(source)
        first_page = reader.pages[0].extract_text() or ''
        text = norm(first_page)
        if 'hsbc' not in text:
            continue
        files.append((source, raw, len(reader.pages), text, norm(first_page[-900:])))
    except Exception:
        continue
state = State(BASE / '.collector')
results = []
for item in catalog:
    doc_id = item['source_url'].rsplit('/',1)[-1]
    report = Report('HSBC',doc_id,item['title'],item['date'],item['source_url'],item['source_url'],published=item['date'])
    result = dict(house='HSBC',doc_id=doc_id,title=item['title'],published=item['date'],url=item['source_url'],pages=int(item['pages']))
    prior = state.db.execute('SELECT * FROM reports WHERE house=? AND doc_id=?', ('HSBC',doc_id)).fetchone()
    if prior and state.downloaded(report):
        prior_reader=PdfReader(prior['path'])
        assert norm(item['title']) in norm((prior_reader.pages[0].extract_text() or '')[-900:]), 'Stored title-region mismatch: '+doc_id
        result.update(status='downloaded',path=prior['path'],bytes=prior['bytes'],sha256=prior['sha256'],listed_pages=int(item['pages']),pages=len(prior_reader.pages))
        results.append(result)
        continue
    stamp = date.fromisoformat(item['date'])
    date_key = norm(f'{stamp.day} {stamp.strftime("%B %Y")}')
    # Some thematic covers show only the month; retain the observed list date.
    month_key = norm(stamp.strftime('%B %Y'))
    unique_title = sum(norm(r['title']) == norm(item['title']) for r in catalog) == 1
    # The HSBC cover's title/author/date block is at the end of extracted text.
    # Never identify a PDF by report titles cited in its narrative or references.
    matches = [f for f in files if f[2] in (int(item['pages']),int(item['pages'])+1) and norm(item['title']) in f[4] and
               (date_key in f[3] or (unique_title and month_key in f[3]))]
    hashes = {hashlib.sha256(f[1]).hexdigest() for f in matches}
    if not matches:
        result['status'] = 'pending_pdf' if int(item['pages'])>1 else 'check_pdf_availability'
        if doc_id in non_pdf_ids:
            reason = 'HTML newsletter; no own original PDF control.' if '/O/' in item['source_url'] else 'Video/podcast player; no separate original PDF. Related full reports, where offered, are separate catalog items already saved.'
            result.update(status='no_original_pdf',reason=reason)
            state.record(report)
            existing = state.db.execute('SELECT status FROM reports WHERE house=? AND doc_id=?',('HSBC',doc_id)).fetchone()
            if existing['status']!='no_original_pdf':
                state.result(report,'no_original_pdf',error=reason)
    elif len(hashes)>1:
        result.update(status='needs_review',error='Multiple different originals matched')
    else:
        source,raw,pages,_,_ = matches[0]
        target = BASE / 'outdated/HSBC' / safe_filename(item['title'],doc_id,stamp)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=raw:
            raise SystemExit('Refusing overwrite: '+str(target))
        if not target.exists():
            with target.open('xb') as f:
                f.write(raw)
            shutil.copystat(source,target)
        assert target.read_bytes()==raw
        state.record(report)
        state.result(report,'downloaded',path=target,raw=raw)
        result.update(status='downloaded',path=str(target),original_download=str(source),bytes=len(raw),sha256=next(iter(hashes)),listed_pages=int(item['pages']),pages=pages)
    results.append(result)
state.export()
state.db.close()
(BASE / '.collector/browser_hsbc_verified_20260901_20260907.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for item,result in zip(catalog,results):
    item['status'] = result['status']
    item['saved_path'] = result.get('path','')
with (BASE / '.collector/browser_hsbc_20260901_20260907.csv').open('w',encoding='utf-8',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(catalog[0]))
    writer.writeheader()
    writer.writerows(catalog)
print(json.dumps({'saved':sum(r['status']=='downloaded' for r in results),'no_original_pdf':sum(r['status']=='no_original_pdf' for r in results),'unresolved':[r['doc_id'] for r in results if r['status'] not in ('downloaded','no_original_pdf')]},ensure_ascii=False))
