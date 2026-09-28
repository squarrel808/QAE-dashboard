"""Register BofA original PDFs from the observed 2026 browser catalog."""
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from pypdf import PdfReader

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from macro_bulk_downloader import Report,State,is_pdf,safe_filename

catalog=list(csv.DictReader((BASE/'.collector/year_2026_bofa_browser_catalog.tsv').open(encoding='utf-8'),delimiter='\t'))
by_id={r['id']:r for r in catalog}
state=State(BASE/'.collector')
new=[]
for source in Path(r'C:\Users\infomax\Downloads').glob('*.tmp'):
    if source.stat().st_mtime<datetime(2026,9,7).timestamp():
        continue
    raw=source.read_bytes()
    if not is_pdf(raw):
        continue
    reader=PdfReader(io.BytesIO(raw))
    text=reader.pages[0].extract_text() or ''
    ids=[doc_id for doc_id in by_id if re.search(r'(?<!\d)'+doc_id+r'(?!\d)',text)]
    if len(ids)!=1:
        continue
    r=by_id[ids[0]]
    report=Report('BofA',r['id'],r['title'],r['publication_date'],'https://markets.ml.com/economics-overview','https://markets.ml.com/economics-overview',region=r['regions'],published=r['publication_date'])
    state.record(report)
    if state.downloaded(report):
        continue
    target=BASE/'outdated/BofA'/safe_filename(r['title'],r['id'],date.fromisoformat(r['publication_date']))
    if target.exists():
        assert target.read_bytes()==raw, 'Refusing different existing target: '+str(target)
    else:
        with target.open('xb') as stream:
            stream.write(raw)
    assert target.read_bytes()==raw
    for page in reader.pages:
        content=page.get_contents()
        if content is not None:
            content.get_data()
    state.result(report,'downloaded',path=target,raw=raw)
    new.append(r['id'])
state.export()
rows=[dict(r) for r in state.db.execute("SELECT house,doc_id,title,published,path,bytes,sha256,status FROM reports WHERE published BETWEEN '2026-01-01' AND '2026-09-07' ORDER BY house,published,doc_id")]
counts={house:sum(r['house']==house and r['status']=='downloaded' for r in rows) for house in ['HSBC','GS','JPM','Citi','BofA']}
saved_ids={r['doc_id'] for r in rows if r['house']=='BofA' and r['status']=='downloaded'}
pending=[r['id'] for r in catalog if r['id'] not in saved_ids]
progress={'start':'2026-01-01','end':'2026-09-07','status':'in_progress','catalog_complete':False,'downloaded':sum(counts.values()),'by_house':counts,'new_bofa_ids':new,'pending_observed_bofa_ids':pending,'records':rows}
(BASE/'.collector/year_2026_progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf-8')
state.db.close()
print(json.dumps({k:v for k,v in progress.items() if k!='records'},ensure_ascii=False))
