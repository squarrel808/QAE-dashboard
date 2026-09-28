"""Read-only consistency checks for the local research index."""
import json
from pathlib import Path
from research_context import BASE, connect, evidence_norm, search


def main():
    db = connect(BASE / 'data', readonly=True)
    result = {'quick_check': db.execute('PRAGMA quick_check').fetchone()[0]}
    for table in ['documents', 'files', 'pages', 'chunks', 'chunks_fts', 'claims']:
        result[table] = db.execute('SELECT count(*) FROM ' + table).fetchone()[0]
    result['document_page_sum'] = db.execute('SELECT sum(pages) FROM documents').fetchone()[0]
    result['missing_source_files'] = sum(not Path(row[0]).is_file() for row in db.execute('SELECT path FROM files'))
    result['file_status'] = dict(db.execute('SELECT status,count(*) FROM files GROUP BY status'))
    result['claim_status'] = dict(db.execute('SELECT review_status,count(*) FROM claims GROUP BY review_status'))
    bad = []
    for row in db.execute('SELECT c.*,p.text FROM claims c LEFT JOIN pages p ON c.doc_id=p.doc_id AND c.page=p.page'):
        if not row['text'] or evidence_norm(row['evidence_quote']) not in evidence_norm(row['text']):
            bad.append(row['claim_id'])
    result['invalid_claim_quotes'] = bad
    hits = search(db, 'inflation', country='EA', asof='2026-08-01', limit=5)
    result['asof_search_hits'] = len(hits)
    result['asof_search_dates'] = [h['published'] for h in hits]
    result['fts_mapping_mismatches'] = db.execute('SELECT count(*) FROM chunks c LEFT JOIN chunks_fts f ON c.chunk_id=f.rowid WHERE f.rowid IS NULL OR c.text!=f.text').fetchone()[0]
    assert result['quick_check'] == 'ok', result
    assert result['pages'] == result['document_page_sum'], result
    assert result['chunks'] == result['chunks_fts'], result
    assert not result['missing_source_files'] and not result['fts_mapping_mismatches'], result
    assert not result['invalid_claim_quotes'] and hits, result
    assert all(h['published'] <= '2026-08-01' for h in hits), result
    db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
