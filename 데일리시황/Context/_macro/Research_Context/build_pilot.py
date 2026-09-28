"""Render the dated, manually selected pilot. This is not a live forecasting model."""
import json
from pathlib import Path
from research_context import BASE, connect, evidence_norm, now


def main():
    items = json.loads((BASE / 'pilot_claims.json').read_text(encoding='utf-8'))
    db = connect(BASE / 'data', readonly=True)
    sources = {}
    ledger = []
    for item in items:
        page = db.execute('SELECT text FROM pages WHERE doc_id=? AND page=?',
                          (item['doc_id'], item['page'])).fetchone()
        if not page or evidence_norm(item['evidence_quote']) not in evidence_norm(page['text']):
            raise ValueError('Source quote mismatch: ' + item['claim_id'])
        saved = db.execute('SELECT review_status FROM claims WHERE claim_id=?',
                           (item['claim_id'],)).fetchone()
        if not saved or saved['review_status'] != 'draft':
            raise ValueError('Import draft claims first: ' + item['claim_id'])
        if item['doc_id'] not in sources:
            doc = db.execute('SELECT * FROM documents WHERE doc_id=?', (item['doc_id'],)).fetchone()
            file = db.execute("SELECT path FROM files WHERE doc_id=? AND status IN ('indexed','alias') LIMIT 1",
                              (item['doc_id'],)).fetchone()
            sources[item['doc_id']] = (len(sources) + 1, dict(doc), Path(file[0]).as_posix())
        number = sources[item['doc_id']][0]
        ledger.append(f"### {item['claim_id']}\n\n{item['claim']} [{number}], p.{item['page']}\n\n> {item['evidence_quote']}\n\n전제·주의: {item['assumptions']}\n\n변경 이력: {item['change_vs_prior']}")
    links = [f"[{num}] **{doc['house']} · {doc['published']}** — [{doc['title']}](<{path}>) · 1페이지."
             for num, doc, path in sources.values()]
    text = (BASE / 'pilot_note.md').read_text(encoding='utf-8')
    text = text.replace('{{SOURCE_LINKS}}', '\n\n'.join(links))
    text = text.replace('{{CLAIM_LEDGER}}', '\n\n'.join(ledger))
    text += f'\n\n작성: {now()} · 모든 견해 상태: 검토 초안.\n'
    target = BASE / 'output' / '02_유로존_IB견해_초기검토.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')
    db.close()
    print(target)


if __name__ == '__main__':
    main()
