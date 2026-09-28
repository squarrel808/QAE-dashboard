"""Local, incremental macro research index. Never calls an API or changes source PDFs."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, date
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import textwrap
import uuid

BASE = Path(__file__).resolve().parent
RAW_DEFAULT = BASE.parent / 'outdated'
PRIORITY = ['US', 'GB', 'EA', 'CA', 'AU']
COUNTRIES = {
 'US': ('미국', r'\b(?:US|U\.S\.|United States|Fed|FOMC|America[n]?)\b'),
 'GB': ('영국', r'\b(?:UK|U\.K\.|United Kingdom|Britain|British|BoE)\b'),
 'EA': ('유로존', r'\b(?:Euro area|Eurozone|Euro zone|Euroland|ECB)\b'),
 'DE': ('독일', r'\bGerman(?:y)?\b'), 'FR': ('프랑스', r'\b(?:France|French)\b'),
 'IT': ('이탈리아', r'\b(?:Italy|Italian)\b'), 'ES': ('스페인', r'\b(?:Spain|Spanish)\b'),
 'CA': ('캐나다', r'\b(?:Canada|Canadian|BoC|Bank of Canada)\b'),
 'AU': ('호주', r'\b(?:Australia[n]?|RBA)\b'), 'NZ': ('뉴질랜드', r'\b(?:New Zealand|RBNZ)\b'),
 'JP': ('일본', r'\b(?:Japan(?:ese)?|BoJ)\b'), 'CN': ('중국', r'\b(?:China|Chinese|PBoC)\b'),
 'KR': ('한국', r'\b(?:Korea[n]?|BoK)\b'), 'TW': ('대만', r'\bTaiwan(?:ese)?\b'),
 'IN': ('인도', r'\b(?:India[n]?|RBI)\b'), 'BR': ('브라질', r'\bBrazil(?:ian)?\b'),
 'MX': ('멕시코', r'\b(?:Mexico|Mexican|Banxico)\b'),
 'CH': ('스위스', r'\b(?:Switzerland|Swiss|SNB)\b'),
 'SE': ('스웨덴', r'\b(?:Sweden|Swedish|Riksbank)\b'),
 'NO': ('노르웨이', r'\b(?:Norway|Norwegian|Norges)\b'),
 'GLOBAL': ('글로벌·복수지역', r'\b(?:Global|World|G10|G7|G20|EM|Emerging Markets|International)\b'),
 'EUROPE': ('유럽 광역', r'\bEurope(?:an)?\b'),
}
TOPICS = {
 'growth': ('성장·경기', r'\b(?:growth|GDP|recession|activity|PMI|ISM|production|consumption|retail|demand|sentiment|ifo)\b'),
 'inflation': ('물가', r'\b(?:inflation|CPI|PCE|HICP|prices|disinflation|deflation|IPCA)\b'),
 'labor': ('고용·임금', r'\b(?:labor|labour|wage[s]?|employment|unemployment|payroll[s]?|job[s]?|hiring)\b'),
 'monetary_policy': ('통화정책', r'\b(?:central bank|Fed|FOMC|ECB|BoE|BoC|RBA|BoJ|policy rate|rate cut[s]?|rate hike[s]?|monetary|hawkish|dovish)\b'),
 'fiscal': ('재정·정치', r'\b(?:fiscal|budget|deficit|government|election[s]?|political|spending|tax|debt)\b'),
 'trade': ('무역·관세', r'\b(?:trade|tariff[s]?|export[s]?|import[s]?|current account|balance of payments)\b'),
 'housing': ('주택·부동산', r'\b(?:housing|house prices|mortgage|property|real estate)\b'),
 'markets': ('금융시장', r'\b(?:FX|currency|currencies|bond[s]?|yield[s]?|equities|equity|credit|financial conditions)\b'),
 'energy': ('에너지·원자재', r'\b(?:oil|gas|energy|commodity|commodities|copper|gold)\b'),
}


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def norm(text):
    return ' '.join(str(text).split())


def evidence_norm(text):
    # Some PDF bullet fonts extract as a standalone 'n' between wrapped lines.
    # Only remove complete marker lines; preserve words, figures and inline 'n'.
    return norm(re.sub(r'(?m)^[ \t]*(?:n|[•◆▪])[ \t]*\r?$', '', str(text)))


def md(text):
    return norm(text).replace('|', '\\|').replace('[', '\\[').replace(']', '\\]')


def valid_date(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        return None


def filename_date(name):
    match = re.match(r'^(\d{4})-?(\d{2})-?(\d{2})[_ -]', name)
    return valid_date('-'.join(match.groups())) if match else None


def filename_title(name):
    name = re.sub(r'^\d{4}-?\d{2}-?\d{2}[_ -]*', '', Path(name).stem)
    return re.sub(r'__(?:[a-fA-F0-9]{12}|GPS-\d+-\d+)$', '', name).replace('_', ' ')


def path_key(path):
    return os.path.normcase(os.path.abspath(path))


def classify(title):
    countries = {code: 'title_match' for code, (_, rule) in COUNTRIES.items() if re.search(rule, title, re.I)}
    if set(countries) & {'DE', 'FR', 'IT', 'ES'}:
        countries.setdefault('EA', 'eurozone_member_in_title')
    topics = {code: 'title_match' for code, (_, rule) in TOPICS.items() if re.search(rule, title, re.I)}
    return countries, topics


def chunks(text, size=1600, overlap=180):
    # Preserve full pages elsewhere. Exclude explicitly headed disclosure sections from search chunks.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.fullmatch(r'\s*(?:Important (?:Disclosures|disclosures)|Analyst Certification|Analyst certification|Disclosures and Disclaimers|Global Disclosures|Legal Disclaimer)\s*', line):
            lines = lines[:i]
            break
    clean = norm('\n'.join(lines))
    if len(clean) < 60:
        return []
    result = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            boundary = clean.rfind(' ', start + size // 2, end)
            if boundary > start:
                end = boundary
        result.append(clean[start:end])
        if end == len(clean):
            break
        start = max(start + 1, end - overlap)
    return result


@contextmanager
def lock_file(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'index.lock').open('a+b') as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def connect(root, readonly=False):
    path = root / 'research.sqlite3'
    if readonly:
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    else:
        root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript('''
          CREATE TABLE IF NOT EXISTS documents(
            doc_id TEXT PRIMARY KEY, sha256 TEXT UNIQUE, house TEXT, title TEXT,
            published TEXT, date_basis TEXT, date_review INTEGER, pages INTEGER,
            text_chars INTEGER, status TEXT, first_ingested TEXT, pipeline_version TEXT);
          CREATE TABLE IF NOT EXISTS files(
            path TEXT PRIMARY KEY, doc_id TEXT, bytes INTEGER, mtime_ns INTEGER,
            sha256 TEXT, status TEXT, error TEXT, last_seen TEXT);
          CREATE TABLE IF NOT EXISTS pages(
            doc_id TEXT, page INTEGER, text TEXT, chars INTEGER, PRIMARY KEY(doc_id,page));
          CREATE TABLE IF NOT EXISTS chunks(
            chunk_id INTEGER PRIMARY KEY, doc_id TEXT, page INTEGER, ordinal INTEGER, text TEXT);
          CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, tokenize='unicode61');
          CREATE TABLE IF NOT EXISTS tags(
            doc_id TEXT, kind TEXT, value TEXT, basis TEXT, PRIMARY KEY(doc_id,kind,value));
          CREATE TABLE IF NOT EXISTS claims(
            claim_id TEXT PRIMARY KEY, doc_id TEXT, page INTEGER, country TEXT, topic TEXT,
            claim TEXT, evidence_quote TEXT, assumptions TEXT, change_vs_prior TEXT,
            review_status TEXT, created_at TEXT);
          CREATE TABLE IF NOT EXISTS runs(
            run_id TEXT PRIMARY KEY, started TEXT, finished TEXT, raw_root TEXT, summary TEXT);
          CREATE INDEX IF NOT EXISTS docs_house_date ON documents(house,published);
          CREATE INDEX IF NOT EXISTS tags_value ON tags(kind,value);
          CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id,page);
          CREATE TABLE IF NOT EXISTS state_memos(
            memo_id TEXT PRIMARY KEY, country TEXT, as_of TEXT, text TEXT,
            review_status TEXT, created_at TEXT);
        ''')
    db.row_factory = sqlite3.Row
    return db


def collector_metadata(raw):
    path = raw.parent / '.collector/downloads.sqlite3'
    if not path.exists():
        return {}
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        return {path_key(r['path']): dict(r) for r in conn.execute(
            'SELECT house,title,published,path,sha256 FROM reports WHERE status=? AND path<>?',
            ('downloaded', ''))}


def choose_metadata(path, raw, meta):
    entry = meta.get(path_key(path), {})
    parent = path.relative_to(raw).parts[0] if len(path.relative_to(raw).parts) > 1 else 'Unknown'
    title = entry.get('title') or filename_title(path.name)
    candidate = valid_date(entry.get('published'))
    file_day = filename_date(path.name)
    conflict = bool(candidate and file_day and candidate != file_day)
    return dict(house=entry.get('house') or parent, title=norm(title),
                published=candidate or file_day,
                date_basis='collector_publication_date' if candidate else 'filename_candidate' if file_day else 'unknown',
                date_review=int(conflict or not candidate))


def ingest(raw, data, output, limit=0):
    import pymupdf as fitz
    raw = raw.resolve()
    if not raw.is_dir():
        raise ValueError('Source PDF folder does not exist: ' + str(raw))
    with lock_file(data):
        db = connect(data)
        run_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
        started = now()
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (run_id, started, None, str(raw), '{}'))
        db.commit()
        meta = collector_metadata(raw)
        paths = sorted(p for p in raw.rglob('*') if p.is_file() and p.suffix.lower() == '.pdf')
        if limit:
            paths = paths[:limit]
        stats = Counter(snapshot_files=len(paths))
        for i, path in enumerate(paths, 1):
            path = path.resolve()
            try:
                st = path.stat()
                previous = db.execute('SELECT * FROM files WHERE path=?', (str(path),)).fetchone()
                if previous and previous['status'] in ('indexed','alias') and previous['bytes'] == st.st_size and previous['mtime_ns'] == st.st_mtime_ns:
                    db.execute('UPDATE files SET last_seen=? WHERE path=?', (started, str(path)))
                    stats['unchanged'] += 1
                    continue
                payload = path.read_bytes()
                after = path.stat()
                if (st.st_size, st.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    stats['deferred_changing'] += 1
                    continue
                if not payload[:1024].lstrip().startswith(b'%PDF-') or b'%%EOF' not in payload[-8192:]:
                    raise ValueError('PDF header/trailer missing; not indexing as a finished document')
                digest = hashlib.sha256(payload).hexdigest()
                doc_id = digest
                info = choose_metadata(path, raw, meta)
                existing = db.execute('SELECT * FROM documents WHERE sha256=?', (digest,)).fetchone()
                if existing:
                    db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?,?,?)',
                        (str(path), existing['doc_id'], st.st_size, st.st_mtime_ns, digest, 'alias', '', started))
                    # Prefer collector metadata over a generic copy filename, not directory sort order.
                    upgrade = existing['date_basis'] != 'collector_publication_date' and (
                        info['date_basis'] == 'collector_publication_date' or (
                            not classify(existing['title'])[0] and bool(classify(info['title'])[0])))
                    if upgrade:
                        db.execute('UPDATE documents SET house=?,title=?,published=?,date_basis=?,date_review=? WHERE doc_id=?',
                                   (info['house'],info['title'],info['published'],info['date_basis'],info['date_review'],doc_id))
                    country_tags, topic_tags = classify(info['title'])
                    for kind, items in [('country',country_tags),('topic',topic_tags)]:
                        db.executemany('INSERT OR IGNORE INTO tags VALUES(?,?,?,?)',
                                       [(doc_id,kind,k,'alias_'+v) for k,v in items.items()])
                    stats['duplicate_content'] += 1
                    db.commit()
                    continue
                with fitz.open(stream=payload, filetype='pdf') as pdf:
                    if pdf.needs_pass:
                        raise ValueError('Password-protected PDF; manual access required')
                    texts = [p.get_text('text', sort=False) for p in pdf]
                chars = sum(len(t.strip()) for t in texts)
                status = 'indexed' if chars >= 120 else 'needs_ocr'
                with db:
                    db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (doc_id,digest,info['house'],info['title'],info['published'],info['date_basis'],info['date_review'],len(texts),chars,status,started,'1.0'))
                    for page_no, text in enumerate(texts,1):
                        db.execute('INSERT INTO pages VALUES(?,?,?,?)', (doc_id,page_no,text,len(text)))
                        for ordinal, chunk in enumerate(chunks(text)):
                            cur = db.execute('INSERT INTO chunks(doc_id,page,ordinal,text) VALUES(?,?,?,?)', (doc_id,page_no,ordinal,chunk))
                            db.execute('INSERT INTO chunks_fts(rowid,text) VALUES(?,?)', (cur.lastrowid,chunk))
                    country_tags, topic_tags = classify(info['title'])
                    for kind, items in [('country',country_tags),('topic',topic_tags)]:
                        db.executemany('INSERT INTO tags VALUES(?,?,?,?)', [(doc_id,kind,k,v) for k,v in items.items()])
                    db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?,?,?)',
                        (str(path),doc_id,st.st_size,st.st_mtime_ns,digest,'indexed' if status=='indexed' else 'needs_ocr','',started))
                stats['new_documents'] += 1
                stats['pages'] += len(texts)
                if status == 'needs_ocr':
                    stats['needs_ocr'] += 1
            except Exception as exc:
                db.rollback()
                stats['failed'] += 1
                with db:
                    db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?,?,?)',
                        (str(path),None,0,0,'','failed',type(exc).__name__+': '+str(exc)[:350],started))
                print('ERROR', path.name, str(exc)[:150], flush=True)
            finally:
                if i % 100 == 0:
                    db.commit()
                    print(json.dumps({'processed':i,'total':len(paths),**dict(stats)},ensure_ascii=False),flush=True)
        db.commit()
        summary = dict(stats)
        summary['current_raw_files'] = sum(1 for p in raw.rglob('*') if p.is_file() and p.suffix.lower()=='.pdf')
        summary['run_id'] = run_id
        summary['source_snapshot_at'] = started
        with db:
            db.execute('UPDATE runs SET finished=?,summary=? WHERE run_id=?',(now(),json.dumps(summary),run_id))
        report(db, output, summary)
        db.close()
        print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
        return summary


def report(db, output, summary=None):
    output.mkdir(parents=True,exist_ok=True)
    rows = db.execute('SELECT house,count(*) n,sum(pages) pages,min(published) first,max(published) last,sum(date_review) date_review FROM documents GROUP BY house ORDER BY house').fetchall()
    total = db.execute('SELECT count(*) n,sum(pages) pages,sum(text_chars) chars FROM documents').fetchone()
    lines=['# 매크로 리서치 — 로컬 적재 현황', '',f'작성 시각: {now()}', '',
           '**이 파일은 데이터 준비 현황이다. IB 견해의 요약·승인이나 3개월 전체 수집 완료를 의미하지 않는다.**', '',
           f"중복 제거 문서 **{total['n']:,}개**, 원문 **{total['pages'] or 0:,}페이지**를 보관했다.", '',
           '| IB | 고유 PDF | 페이지 | 최초 발행일 | 최종 발행일 | 날짜 검토 필요 |',
           '|---|---:|---:|---|---|---:|']
    for row in rows:
        lines.append(f"| {row['house']} | {row['n']} | {row['pages']} | {row['first'] or '미상'} | {row['last'] or '미상'} | {row['date_review']} |")
    lines+=['','발행일 범위 안에도 누락이 있을 수 있다. 검색되지 않은 보고서의 존재 여부는 이 적재 작업으로 검증하지 않았다.', '',
            '## 국가 분류 — 제목에 명시된 국가 기준', '',
            '자동 분류는 검색용 태그이며, 해당 IB의 전망이나 견해를 추론하지 않는다. 독일·프랑스·이탈리아·스페인 제목은 유로존에도 연결한다. 복수 태그 문서는 중복 집계될 수 있다.', '',
            '| 국가/지역 | 문서 수 |', '|---|---:|']
    for row in db.execute("SELECT value,count(*) n FROM tags WHERE kind='country' GROUP BY value ORDER BY n DESC"):
        lines.append(f"| {COUNTRIES.get(row['value'],(row['value'],''))[0]} | {row['n']} |")
    lines+=['','## 수집 월별 공백 확인','','| IB | 발행월 | 문서 수 |','|---|---|---:|']
    for row in db.execute('SELECT house,substr(published,1,7) month,count(*) n FROM documents GROUP BY house,month ORDER BY house,month'):
        lines.append(f"| {row['house']} | {row['month'] or '미상'} | {row['n']} |")
    lines+=['','## 처리 상태','','| 상태 | 파일 수 |','|---|---:|']
    for row in db.execute('SELECT status,count(*) n FROM files GROUP BY status'):
        lines.append(f"| {row['status']} | {row['n']} |")
    failures=[dict(r) for r in db.execute("SELECT path,error FROM files WHERE status='failed'")]
    if failures:
        lines+=['','실패한 파일은 원본을 변경하지 않고 제외했으며 다음 실행에서 재시도한다.']
        lines += [f"- {md(Path(r['path']).name)}: {md(r['error'])}" for r in failures[:30]]
    if summary:
        lines+=['','## 이번 실행','','```json',json.dumps(summary,ensure_ascii=False,indent=2),'```']
    lines+=['','## 다음 단계','','1. 국가별 검토 묶음에서 원문과 페이지 확인.','2. IB의 주장·근거·전제·전망 대상 기간을 구분해 `claims`에 초안 적재.','3. 같은 IB의 이전 견해와 비교해 실제 전망 변경인지 확인.','4. WECO 발표 자료를 넣고 당시 알려진 정보와 최신 해석을 분리해 대조.','5. 국가 판단 메모는 초안과 승인본을 구분. 승인본 자동 덮어쓰기 없음.','',
            '유료 API·임베딩·뉴스 자동 검색·외부 게시·브라우저 조작은 수행하지 않았다.']
    (output/'01_적재현황.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def search(db, text='', country=None, house=None, topic=None, asof=None, limit=10):
    clauses=['d.status=?']; params=['indexed']
    if text:
        base='FROM chunks_fts f JOIN chunks c ON c.chunk_id=f.rowid JOIN documents d ON d.doc_id=c.doc_id'
        clauses.append('chunks_fts MATCH ?'); params.append(text)
        order='bm25(chunks_fts),d.published DESC'
    else:
        base='FROM chunks c JOIN documents d ON d.doc_id=c.doc_id'
        order='d.published DESC,c.page,c.ordinal'
    for kind,val in [('country',country),('topic',topic)]:
        if val:
            clauses.append('EXISTS(SELECT 1 FROM tags t WHERE t.doc_id=d.doc_id AND t.kind=? AND t.value=?)')
            params.extend([kind,val])
    if house:
        clauses.append('d.house=?'); params.append(house)
    if asof:
        if not valid_date(asof):
            raise ValueError('Invalid as-of date')
        clauses.extend(['d.published<=?', 'd.date_review=0']); params.append(asof)
    sql='SELECT d.doc_id,d.house,d.title,d.published,c.page,c.text '+base+' WHERE '+' AND '.join(clauses)+' ORDER BY '+order+' LIMIT ?'
    return [dict(r) for r in db.execute(sql,params+[limit])]


def packet(db, output, country, per_house=8):
    output.mkdir(parents=True,exist_ok=True)
    clauses="EXISTS(SELECT 1 FROM tags t WHERE t.doc_id=d.doc_id AND t.kind='country' AND t.value=?)"
    lines=[f'# {COUNTRIES.get(country,(country,""))[0]} — IB 원문 검토 묶음','',
           '자동 생성 자료집이며 분석 완료본이 아니다. 최신 문서뿐 아니라 과거 문서도 검색해 전망 변경 여부를 검토해야 한다.', '',
           '원문 발췌는 일부 문맥이다. 숫자·조건·전망 대상 연도는 연결된 전체 페이지에서 확인한다. 문서 사이 빈 기간을 견해 유지로 해석하지 않는다.','']
    for house in [r[0] for r in db.execute('SELECT DISTINCT house FROM documents ORDER BY house')]:
        rows=db.execute('SELECT d.* FROM documents d WHERE '+clauses+' AND d.house=? ORDER BY d.published DESC LIMIT ?', (country,house,per_house)).fetchall()
        lines += [f'## {house}','']
        if not rows:
            lines+=['해당 국가로 제목 분류된 문서 없음. 이 IB가 견해를 내지 않았다는 뜻은 아니다.','']; continue
        for row in rows:
            path=db.execute("SELECT path FROM files WHERE doc_id=? AND status IN ('indexed','alias') LIMIT 1",(row['doc_id'],)).fetchone()
            page=db.execute('SELECT page,text FROM pages WHERE doc_id=? AND chars>=120 ORDER BY page LIMIT 1',(row['doc_id'],)).fetchone()
            lines += [f"### {row['published'] or '날짜 미확인'} — {md(row['title'])}",'',
                      f"문서 ID: `{row['doc_id']}` · 발행일 근거: `{row['date_basis']}` · 날짜 검토: {'필요' if row['date_review'] else '불필요(수집 기록 기준)'}",'']
            if path:
                lines += [f"[원본 PDF](<{Path(path[0]).as_posix()}>) · {page['page'] if page else '?'}페이지",'']
            if page:
                excerpt='\n'.join(chunks(page['text'])[:2])[:2600]
                lines += ['> '+line for line in textwrap.wrap(excerpt,120)] + ['']
            lines += ['검토할 필드: 핵심 주장 / 근거·전제 / 전망 대상 기간 / 이전 견해 대비 변화 / 반증 조건.','']
    target=output/f'{country}_{COUNTRIES.get(country,(country,""))[0]}_검토묶음.md'
    target.write_text('\n'.join(lines),encoding='utf-8')
    return target


def import_claims(db, path):
    items=json.loads(path.read_text(encoding='utf-8'))
    validated=[]
    for item in items:
        row=db.execute('SELECT text FROM pages WHERE doc_id=? AND page=?',(item['doc_id'],item['page'])).fetchone()
        quote=evidence_norm(item.get('evidence_quote',''))
        if not row or len(quote)<35 or quote not in evidence_norm(row['text']):
            raise ValueError('Evidence must be a real verbatim excerpt from the cited page: '+item.get('claim_id','unknown'))
        if item['country'] not in COUNTRIES or item['topic'] not in TOPICS:
            raise ValueError('Unknown country/topic')
        validated.append(item)
    with db:
        for item in validated:
            # Immutable: importing a revised interpretation requires a new claim ID.
            db.execute('INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (item['claim_id'],item['doc_id'],item['page'],item['country'],item['topic'],item['claim'],item['evidence_quote'],item.get('assumptions',''),item.get('change_vs_prior','미확인'),'draft',now()))
    return len(validated)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=BASE/'data')
    p.add_argument('--output',type=Path,default=BASE/'output')
    sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('ingest'); q.add_argument('--raw',type=Path,default=RAW_DEFAULT); q.add_argument('--limit',type=int,default=0)
    q=sub.add_parser('search'); q.add_argument('--text',default=''); q.add_argument('--country'); q.add_argument('--house'); q.add_argument('--topic'); q.add_argument('--asof'); q.add_argument('--limit',type=int,default=10)
    q=sub.add_parser('packet'); q.add_argument('--country',default='all'); q.add_argument('--per-house',type=int,default=8)
    sub.add_parser('status')
    q=sub.add_parser('import-claims'); q.add_argument('json_file',type=Path)
    args=p.parse_args(argv); args.data=args.data.resolve(); args.output=args.output.resolve()
    if args.command=='ingest':
        ingest(args.raw,args.data,args.output,args.limit); return
    db=connect(args.data,readonly=args.command!='import-claims')
    try:
        if args.command=='search':
            print(json.dumps(search(db,args.text,args.country,args.house,args.topic,args.asof,args.limit),ensure_ascii=False,indent=2))
        elif args.command=='packet':
            for country in PRIORITY if args.country=='all' else [args.country]:
                print(packet(db,args.output/'country_packets',country,args.per_house))
        elif args.command=='status':
            print(json.dumps([dict(r) for r in db.execute('SELECT house,count(*) n,min(published) first,max(published) last FROM documents GROUP BY house')],ensure_ascii=False,indent=2))
        elif args.command=='import-claims':
            print('Draft claims imported:',import_claims(db,args.json_file))
    finally:
        db.close()


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
