"""Reconcile observed GS catalog against complete original Chrome downloads."""
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
    value = re.sub(r'\s*\((?:Ramos|Hatzius|\d+)\)\s*$', '', value or '', flags=re.I)
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum())

catalog = []
for line in (BASE / '.collector/gs_browser_catalog_20260901_20260907.txt').read_text(encoding='utf-8').splitlines():
    day, pages, url, title = line.split('|', 3)
    if not url.startswith('https://'):
        url = 'https://marquee.gs.com/content/research/en/' + url
    catalog.append(dict(doc_id=url.rsplit('/', 1)[-1].removesuffix('.html'), published=f'2026-09-{int(day):02}', title=title, pages=int(pages), url=url))
assert len(catalog) == len({r['doc_id'] for r in catalog}) == 118
non_pdf = json.loads((BASE / '.collector/gs_non_pdf_20260907.json').read_text(encoding='utf-8'))
files = []
for source in Path(r'C:\Users\infomax\Downloads').glob('*.pdf'):
    if source.name.startswith(('GPS-', 'print')) or source.stat().st_mtime < datetime(2026, 9, 7).timestamp():
        continue
    raw = source.read_bytes()
    if not is_pdf(raw):
        continue
    try:
        reader = PdfReader(source)
        meta = reader.metadata or {}
        if not any('quark' in str(v).lower() or 'goldman sachs' in str(v).lower() for v in meta.values()):
            continue
        files.append((source, raw, len(reader.pages), {norm(source.stem), norm(meta.get('/Title', ''))}))
    except Exception:
        continue
results = []
state = State(BASE / '.collector')
for item in catalog:
    result = dict(house='GS', **item)
    report = Report('GS', item['doc_id'], item['title'], item['published'], item['url'], item['url'], published=item['published'])
    # GS truncates long PDF metadata and download filenames. Accept a long
    # prefix only when it uniquely identifies one observed catalog title.
    def matches(keys):
        wanted = norm(item['title'])
        return wanted in keys or any(len(k) >= 100 and wanted.startswith(k) and
            sum(norm(r['title']).startswith(k) for r in catalog) == 1 for k in keys)
    candidates = [f for f in files if matches(f[3]) and item['pages'] == f[2]]
    if not candidates:
        result['status'] = 'pending_pdf' if item['pages'] > 1 else 'check_pdf_availability'
        if item['doc_id'] in non_pdf:
            result.update(status='no_original_pdf', reason=non_pdf[item['doc_id']])
            state.record(report)
            existing = state.db.execute('SELECT status FROM reports WHERE house=? AND doc_id=?', ('GS', item['doc_id'])).fetchone()
            if existing['status'] != 'no_original_pdf':
                state.result(report, 'no_original_pdf', error=result['reason'])
        elif item['doc_id'] == 'f2bb28c1-bdf3-48c2-b8d1-8e0c57442e1c':
            result.update(status='unresolved_print_control', reason='53:09 audio and HTML agenda. Print PDF click timed out; no original PDF downloaded. Webpage was not converted to PDF.')
            state.record(report)
            existing = state.db.execute('SELECT status FROM reports WHERE house=? AND doc_id=?', ('GS', item['doc_id'])).fetchone()
            if existing['status'] != result['status']:
                state.result(report, result['status'], error=result['reason'])
    elif len({hashlib.sha256(f[1]).hexdigest() for f in candidates}) > 1:
        result.update(status='needs_review', error='Different original PDFs with matching title')
    else:
        source, raw, pages, _ = candidates[0]
        target = BASE / 'outdated/GS' / safe_filename(item['title'], item['doc_id'], date.fromisoformat(item['published']))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise SystemExit('Refusing overwrite: ' + str(target))
        if not target.exists():
            with target.open('xb') as f:
                f.write(raw)
            shutil.copystat(source, target)
        assert target.read_bytes() == raw
        state.record(report)
        if not state.downloaded(report):
            state.result(report, 'downloaded', path=target, raw=raw)
        result.update(status='downloaded', path=str(target), original_download=str(source), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    results.append(result)
state.export()
state.db.close()
(BASE / '.collector/browser_gs_20260901_20260907.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'files':len(files), 'saved':sum(r['status']=='downloaded' for r in results), 'no_original_pdf':sum(r['status']=='no_original_pdf' for r in results), 'unresolved':[{k:r[k] for k in ('doc_id','title','pages','status')} for r in results if r['status'] not in ('downloaded','no_original_pdf')]}, ensure_ascii=False))
