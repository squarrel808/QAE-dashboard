"""Validate original PDF download artifacts and copy only this run's BofA report IDs."""
import csv
import hashlib
import io
import json
import re
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader

base = Path(__file__).resolve().parent
out = base.parent / 'outdated' / 'BofA'
out.mkdir(parents=True, exist_ok=True)
with (base / 'manual_bofa_20260907.tsv').open(encoding='utf-8') as stream:
    rows = list(csv.DictReader(stream, delimiter='\t'))
manifest = base / 'manual_bofa_20260907_manifest.json'
saved = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
existing_ids = {row['id'] for row in saved}
new = []
cutoff = datetime(2026, 9, 7, 17, 45).timestamp()
for source in sorted(Path(r'C:\Users\infomax\Downloads').glob('*.tmp')):
    if source.stat().st_mtime < cutoff:
        continue
    data = source.read_bytes()
    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-4096:]:
        continue
    reader = PdfReader(io.BytesIO(data))
    first_page = reader.pages[0].extract_text() or ''
    matches = [row for row in rows if re.search(r'(?<!\d)' + row['id'] + r'(?!\d)', first_page)]
    if len(matches) != 1:
        continue
    row = matches[0]
    if row['id'] in existing_ids:
        continue
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', row['title'])
    title = re.sub(r'\s+', ' ', title)[:100].strip().rstrip('.')
    target = out / (row['publication_date'] + '_' + title + '__' + row['id'] + '.pdf')
    digest = hashlib.sha256(data).hexdigest()
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Different existing target: ' + str(target))
    else:
        with target.open('xb') as stream:
            stream.write(data)
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Copy mismatch: ' + str(target))
    record = dict(row, source_list='https://markets.ml.com/economics-overview', original_download=str(source), saved_path=str(target), sha256=digest, bytes=len(data), pages=len(reader.pages), status='downloaded_original_pdf')
    saved.append(record)
    new.append(row['id'])
    existing_ids.add(row['id'])
manifest.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'downloaded':len(saved),'new':new,'missing':[row['id'] for row in rows if row['id'] not in existing_ids]},ensure_ascii=False))
