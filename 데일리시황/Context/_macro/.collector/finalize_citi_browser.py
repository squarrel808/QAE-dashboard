"""Match browser downloads to the observed Citi catalog, verify and register."""
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from macro_bulk_downloader import Report, State, is_pdf, safe_filename

def norm(value):
    return re.sub(r"\s+", " ", value or "").strip()

catalog = json.loads((BASE / '.collector/citi_browser_catalog_20260901_20260907.json').read_text(encoding='utf-8'))
downloads = Path(r'C:\Users\infomax\Downloads')
files = {}
for source in downloads.glob('print*.pdf'):
    raw = source.read_bytes()
    if is_pdf(raw):
        try:
            reader = PdfReader(source)
            files.setdefault(norm(reader.metadata.title), []).append((source, raw, len(reader.pages)))
        except Exception:
            pass
state = State(BASE / '.collector')
results = []
for doc_id, published, title in catalog:
    url = f'https://www.citivelocity.com/cv2/smartlink/research/{doc_id}?menuCode=MarketBuzz_OV'
    report = Report('Citi', doc_id, title, published, url, url, published=published)
    candidates = files.get(norm(title), [])
    result = dict(house='Citi', doc_id=doc_id, published=published, title=title, url=url)
    if not candidates:
        result['status'] = 'pending'
        results.append(result)
        continue
    hashes = {hashlib.sha256(raw).hexdigest() for _,raw,_ in candidates}
    if len(hashes) != 1:
        result.update(status='needs_review', error='Multiple different PDFs with matching title')
        results.append(result)
        continue
    source, raw, pages = candidates[0]
    target = BASE / 'outdated/Citi' / safe_filename(title, doc_id, date.fromisoformat(published))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != raw:
        raise SystemExit('Refusing to overwrite different existing PDF: '+str(target))
    if not target.exists():
        with target.open('xb') as f:
            f.write(raw)
        shutil.copystat(source, target)
    if target.read_bytes() != raw:
        raise SystemExit('Copy mismatch: '+str(target))
    state.record(report)
    if not state.downloaded(report):
        state.result(report, 'downloaded', path=target, raw=raw)
    result.update(status='downloaded', path=str(target), original_download=str(source), bytes=len(raw), pages=pages, sha256=next(iter(hashes)))
    results.append(result)
state.export()
state.db.close()
(BASE / '.collector/browser_citi_20260901_20260907.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'downloaded':sum(r['status']=='downloaded' for r in results),'total':len(results),'pending':[r['doc_id'] for r in results if r['status']!='downloaded']},ensure_ascii=False))
