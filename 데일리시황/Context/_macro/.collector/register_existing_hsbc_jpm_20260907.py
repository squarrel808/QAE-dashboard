"""Register already-downloaded local files only. No browser or network access."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from macro_bulk_downloader import Report, START_URLS, State, is_pdf


def main():
    folder = BASE / '.collector'
    entries = []
    with (folder / 'manual_jpm_20260907_manifest.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 71, f'Expected 71 JPM entries, found {len(rows)}'
    assert len({row['id'] for row in rows}) == 71, 'Duplicate JPM document identifiers'
    for row in rows:
        assert row['house'] == 'JPM' and row['status'] == 'downloaded'
        assert row['id'] == urlparse(row['source_url']).path.rsplit('/', 1)[-1]
        published = date.fromisoformat(row['publication_date'])
        assert date(2026, 9, 1) <= published <= date(2026, 9, 7)
        path = Path(row['saved_path']).resolve(strict=True)
        assert path.is_relative_to((BASE / 'outdated' / 'JPM').resolve())
        raw = path.read_bytes()
        assert is_pdf(raw), f'Invalid PDF: {path}'
        assert len(raw) == int(row['bytes']), f'Byte count mismatch: {path}'
        assert hashlib.sha256(raw).hexdigest().lower() == row['sha256'].lower(), f'Hash mismatch: {path}'
        pages = len(PdfReader(path).pages)
        assert pages > 0
        report = Report('JPM', row['id'], row['title'], row['publication_date'],
                        row['source_url'], START_URLS['JPM'])
        entries.append((report, path, raw, pages))

    hsbc_path = BASE / 'outdated' / 'HSBC' / '2026-09-07_Türkiye MTP__hQdKCJlCxjQZ.pdf'
    hsbc_raw = hsbc_path.read_bytes()
    hsbc_reader = PdfReader(hsbc_path)
    hsbc_text = hsbc_reader.pages[0].extract_text()
    assert is_pdf(hsbc_raw) and len(hsbc_reader.pages) == 6
    assert len(hsbc_raw) == 277609
    assert hashlib.sha256(hsbc_raw).hexdigest() == '5c846587f05b3fcf631bc3dc25054ed34f4cc5cab7eb3dca69880794e02fc78f'
    assert 'Türkiye MTP' in hsbc_text and 'Disinflation disappointment' in hsbc_text
    assert '7 September 2026' in hsbc_text
    assert hsbc_reader.metadata.get('/Schematic') == '97159481:CxjQZ:10'
    hsbc = Report('HSBC', 'hQdKCJlCxjQZ', 'Türkiye MTP — Disinflation disappointment',
                  '07-Sep-26', 'https://www.research.hsbc.com/R/10/hQdKCJlCxjQZ', START_URLS['HSBC'])
    entries.append((hsbc, hsbc_path, hsbc_raw, 6))

    state = State(folder)
    state.db.execute('PRAGMA busy_timeout = 30000')
    before = {(r['house'], r['doc_id']) for r in state.db.execute('SELECT house,doc_id FROM reports')}
    for report, path, raw, pages in entries:
        existing = state.db.execute('SELECT status,path,sha256 FROM reports WHERE house=? AND doc_id=?',
                                    (report.house, report.doc_id)).fetchone()
        if existing and existing['status'] == 'downloaded':
            assert state.downloaded(report), f'Existing downloaded row is invalid: {report.doc_id}'
            assert Path(existing['path']).resolve() == path.resolve(), f'Existing valid row has a different path: {report.doc_id}'
            assert existing['sha256'].lower() == hashlib.sha256(raw).hexdigest()

    results = []
    for report, path, raw, pages in entries:
        already_registered = state.downloaded(report)
        if not already_registered:
            state.record(report)
            state.result(report, 'downloaded', path=path, raw=raw)
        assert state.downloaded(report), f'Registration verification failed: {report.doc_id}'
        results.append({'house': report.house, 'doc_id': report.doc_id, 'published': report.published,
                        'path': str(path), 'bytes': len(raw), 'pages': pages,
                        'sha256': hashlib.sha256(raw).hexdigest(), 'already_registered': already_registered})
    after = {(r['house'], r['doc_id']) for r in state.db.execute('SELECT house,doc_id FROM reports')}
    assert before.issubset(after), 'A pre-existing collector row disappeared'
    state.db.close()
    summary = {'operation': 'register_existing_local_files_only', 'JPM_verified': 71, 'HSBC_verified': 1,
               'new_registrations': sum(not item['already_registered'] for item in results),
               'preserved_existing_keys': len(before), 'entries': results,
               'manifest_export_deferred': True}
    output = folder / 'registered_existing_hsbc_jpm_20260907.json'
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'entries'}, ensure_ascii=True))
    print(str(output))


if __name__ == '__main__':
    main()
