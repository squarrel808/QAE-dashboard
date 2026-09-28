"""Page-grounded IB memory on top of research_context.py. Standard library only.

This program stores reviewed assertions and prepares event evidence. It does not
infer broker opinions from titles, invoke a model, or turn an event into an IB call.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile

HOUSES = ('GS', 'JPM', 'Citi', 'BofA', 'HSBC')
COUNTRIES = {'US': '미국', 'EA': '유로존', 'GB': '영국', 'CA': '캐나다', 'AU': '호주', 'JP': '일본', 'GLOBAL': '글로벌'}
TRACKS = {
    'policy.near_term': '정책금리 기본 전망', 'policy.easing_start': '인하 시작 시점',
    'policy.reaction': '정책 판단 조건', 'inflation.preview': '물가 발표 전 전망',
    'inflation.outlook': '물가 경로', 'inflation.trend': '물가 해석',
    'labor.participation': '경제활동참가율', 'labor.trend': '고용·임금',
    'growth.drivers': '성장 동력', 'growth.risks': '성장 위험', 'growth.trend': '성장 추세',
    'housing.outlook': '주택 전망', 'consumption.trend': '소비', 'productivity.trend': '생산성',
    'energy.risks': '에너지 위험', 'rates.outlook': '시장금리 전망',
}
SCOPES = {'country_research': '국가별 직접 분석', 'cross_region_summary': '다른 지역·글로벌 보고서의 요약', 'rates_and_economics': '금리 전략·경제 분석'}
CHANGE = {'uncompared': '이전 원본과 미대조', 'maintained': '이전 원본 대비 유지', 'revised': '이전 원본 대비 변경'}
DECISIONS = {'FED_DECISION': 'US', 'ECB_DECISION': 'EA', 'BOE_DECISION': 'GB', 'BOC_DECISION': 'CA', 'RBA_DECISION': 'AU', 'BOJ_DECISION': 'JP'}
EVENT_UNITS = {'pct_mom', 'pct_yoy', 'pct_qoq', 'pct_qoq_annualized', 'pct_level', 'thousand_persons', 'persons', 'index', 'bps', 'usd_per_barrel', 'jpy_per_usd'}
NOTE = '전부 사용자 검토 전 초안입니다. 아래는 검토한 자료에서 확인한 최신 견해이며, 해당 IB의 모든 최신 보고서를 검토했다는 뜻은 아닙니다.'
TIME_NOTE = '자료 기준일은 수집 메타데이터의 발행일과 확인한 표지일 중 보수적인 날짜입니다. 정확한 배포 시각·과거 이용 가능 시점은 복원하지 않았습니다.'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def norm(s):
    s = re.sub(r'(?m)^\s*(?:n|o|§|◆|•)\s*$', ' ', s)
    return re.sub(r'\s+', ' ', s.replace('\u00ad', '')).strip()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False, suffix='.tmp') as f:
        tmp = Path(f.name)
        f.write(text)
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(path, data):
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def source_db(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def state_db(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS views(
          view_id TEXT PRIMARY KEY, house TEXT NOT NULL, country TEXT NOT NULL,
          track TEXT NOT NULL, effective_date TEXT NOT NULL, payload TEXT NOT NULL,
          digest TEXT NOT NULL, recorded_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS views_lookup ON views(house,country,track,effective_date);
        CREATE TABLE IF NOT EXISTS imports(
          digest TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, count INTEGER NOT NULL, metadata TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS forecasts(
          forecast_id TEXT PRIMARY KEY, house TEXT NOT NULL, country TEXT NOT NULL,
          indicator TEXT NOT NULL, reference_period TEXT NOT NULL, as_of TEXT NOT NULL,
          unit TEXT NOT NULL, scenario TEXT NOT NULL, payload TEXT NOT NULL,
          digest TEXT NOT NULL, recorded_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS forecasts_lookup ON forecasts(house,country,indicator,reference_period,unit,scenario,as_of);
        CREATE TABLE IF NOT EXISTS forecast_imports(
          digest TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, count INTEGER NOT NULL, metadata TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
          event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL, recorded_at TEXT NOT NULL);
    ''')
    return db


def valid_day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')
    return date.fromisoformat(value)


def all_views(db):
    return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM views ORDER BY effective_date,view_id')]


def all_forecasts(db):
    return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM forecasts ORDER BY as_of,forecast_id')]


def validate_evidence(evidence, house, effective, src, ident):
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f'페이지 근거 누락: {ident}')
    for e in evidence:
        if set(e) != {'doc_id','page','quote'} or type(e['page']) is not int or e['page'] < 1 or not isinstance(e['quote'], str) or not norm(e['quote']):
            raise ValueError(f'근거 형식 오류: {ident}')
        doc = src.execute('SELECT * FROM documents WHERE doc_id=?', (e['doc_id'],)).fetchone()
        page = src.execute('SELECT text FROM pages WHERE doc_id=? AND page=?', (e['doc_id'], e['page'])).fetchone()
        if doc is None or doc['house'] != house or doc['status'] != 'indexed':
            raise ValueError(f'근거 문서/하우스 불일치: {ident}')
        if doc['date_review'] or not doc['published'] or valid_day(doc['published']) > effective:
            raise ValueError(f'발행일 불명/검토 필요/미래 자료: {ident}')
        if page is None or norm(e['quote']) not in norm(page['text']):
            raise ValueError(f'원문 인용 불일치: {ident}, page {e["page"]}')


def validate_views(items, src, existing=()):
    seen = {}
    by_id = {v['view_id']: v for v in existing}
    for v in items:
        required = {'view_id','house','country','track','effective_date','summary','scope','assumptions','watch','analyst_questions','limitations','evidence','prior_view_id','change','change_note','review_status','origin'}
        if set(v) != required:
            raise ValueError(f'견해 필드 오류: {set(v) ^ required}')
        ident = v['view_id']
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', ident):
            raise ValueError('잘못된 view_id')
        if ident in seen:
            raise ValueError(f'입력 내 중복 ID: {ident}')
        seen[ident] = v
        if ident in by_id and canonical(by_id[ident]) != canonical(v):
            raise ValueError(f'기존 견해는 불변입니다. 새 ID와 prior_view_id를 사용하세요: {ident}')
        by_id[ident] = v
        if v['house'] not in HOUSES or v['country'] not in COUNTRIES or v['track'] not in TRACKS:
            raise ValueError(f'하우스/국가/쟁점 오류: {ident}')
        effective = valid_day(v['effective_date'])
        if v['review_status'] != 'draft' or v['origin'] != 'assistant_review_of_local_reports':
            raise ValueError('가져오기는 근거 검토 초안만 허용합니다. 사용자 승인으로 표시하지 않습니다.')
        if v['scope'] not in SCOPES or v['change'] not in CHANGE:
            raise ValueError(f'범위/변경 유형 오류: {ident}')
        for key in ('summary', 'change_note'):
            if not isinstance(v[key], str) or not v[key].strip():
                raise ValueError(f'{key} 누락: {ident}')
        for key in ('assumptions','watch','analyst_questions','limitations'):
            if not isinstance(v[key], list) or not all(isinstance(x, str) and x.strip() for x in v[key]):
                raise ValueError(f'{key} 형식 오류: {ident}')
        if len(v['watch']) != len(set(v['watch'])) or not all(re.fullmatch('[A-Z][A-Z0-9_]+', x) for x in v['watch']):
            raise ValueError(f'지표 ID 오류: {ident}')
        validate_evidence(v['evidence'], v['house'], effective, src, ident)
    for ident, v in by_id.items():
        prior = v['prior_view_id']
        if prior is None:
            if v['change'] != 'uncompared':
                raise ValueError(f'유지/변경 판정에 이전 원본이 필요합니다: {ident}')
            continue
        if not isinstance(prior, str) or prior not in by_id or prior == ident:
            raise ValueError(f'이전 견해 연결 오류: {ident}')
        p = by_id[prior]
        if any(v[k] != p[k] for k in ('house','country','track')) or p['effective_date'] > v['effective_date']:
            raise ValueError(f'이전 견해 범위/시간 오류: {ident}')
        if v['change'] == 'uncompared':
            raise ValueError(f'이전 견해 연결에 유지/변경 판정이 필요합니다: {ident}')
        visited = {ident}
        while prior:
            if prior in visited:
                raise ValueError(f'순환 이력: {ident}')
            visited.add(prior)
            prior = by_id[prior]['prior_view_id']


def import_views(payload, src, state):
    if payload.get('schema_version') != 1 or not isinstance(payload.get('views'), list):
        raise ValueError('schema_version=1 및 views 배열이 필요합니다.')
    asof = valid_day(payload['as_of'])
    if any(valid_day(v['effective_date']) > asof for v in payload['views']):
        raise ValueError('입력 기준일 뒤의 견해가 포함되어 있습니다.')
    # The entire batch is verified before the first insert.
    with state:
        state.execute('BEGIN IMMEDIATE')
        previous = all_views(state)
        validate_views(payload['views'], src, previous)
        before = state.total_changes
        stamp = datetime.now().astimezone().isoformat(timespec='seconds')
        for v in payload['views']:
            blob = canonical(v)
            state.execute('INSERT OR IGNORE INTO views VALUES(?,?,?,?,?,?,?,?)', (v['view_id'], v['house'], v['country'], v['track'], v['effective_date'], blob, hashlib.sha256(blob.encode()).hexdigest(), stamp))
        added = state.total_changes - before
        digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
        metadata = {k: x for k, x in payload.items() if k != 'views'}
        state.execute('INSERT OR IGNORE INTO imports VALUES(?,?,?,?)', (digest,stamp,len(payload['views']),canonical(metadata)))
    return {'added': added, 'unchanged': len(payload['views']) - added, 'total_views': len(all_views(state))}


def validate_forecasts(items, src, existing=()):
    required={'forecast_id','house','country','indicator','reference_period','as_of','unit','value','scenario','qualifier','evidence','prior_forecast_id','change','review_status','origin'}
    seen={};by_id={f['forecast_id']:f for f in existing}
    for f in items:
        if set(f)!=required:raise ValueError(f'전망 필드 오류: {set(f)^required}')
        ident=f['forecast_id']
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,180}',ident):raise ValueError('잘못된 forecast_id')
        if ident in seen:raise ValueError(f'입력 내 중복 ID: {ident}')
        seen[ident]=f
        if ident in by_id and canonical(by_id[ident])!=canonical(f):raise ValueError(f'기존 전망은 불변입니다. 새 ID와 prior_forecast_id를 사용하세요: {ident}')
        by_id[ident]=f
        if f['house'] not in HOUSES or f['country'] not in COUNTRIES:raise ValueError(f'하우스/국가 오류: {ident}')
        asof=valid_day(f['as_of'])
        if not isinstance(f['indicator'],str) or not re.fullmatch(r'[A-Z][A-Z0-9_]+',f['indicator']):raise ValueError(f'지표 ID 오류: {ident}')
        if not isinstance(f['reference_period'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}',f['reference_period']):raise ValueError(f'대상 기간 오류: {ident}')
        if f['unit'] not in EVENT_UNITS or f['scenario'] not in {'base','risk'}:raise ValueError(f'단위/시나리오 오류: {ident}')
        if type(f['value']) not in (int,float) or not math.isfinite(f['value']):raise ValueError(f'전망값 오류: {ident}')
        if not isinstance(f['qualifier'],str) or not f['qualifier'].strip():raise ValueError(f'전망 설명 누락: {ident}')
        if f['change'] not in CHANGE:raise ValueError(f'변경 유형 오류: {ident}')
        if f['review_status']!='draft' or f['origin']!='assistant_review_of_local_reports':raise ValueError('가져오기는 근거 검토 초안만 허용합니다.')
        validate_evidence(f['evidence'],f['house'],asof,src,ident)
    for ident,f in by_id.items():
        prior=f['prior_forecast_id']
        if prior is None:
            if f['change']!='uncompared':raise ValueError(f'전망 비교에 이전 원본이 필요합니다: {ident}')
            continue
        if not isinstance(prior,str) or prior not in by_id or prior==ident:raise ValueError(f'이전 전망 연결 오류: {ident}')
        p=by_id[prior];keys=('house','country','indicator','reference_period','unit','scenario')
        if any(f[k]!=p[k] for k in keys) or p['as_of']>f['as_of']:raise ValueError(f'이전 전망 범위/시간 오류: {ident}')
        if f['change']=='uncompared':raise ValueError(f'이전 전망 연결에 유지/변경 판정이 필요합니다: {ident}')
        visited={ident}
        while prior:
            if prior in visited:raise ValueError(f'순환 전망 이력: {ident}')
            visited.add(prior);prior=by_id[prior]['prior_forecast_id']


def import_forecasts(payload,src,state):
    if payload.get('schema_version')!=1 or not isinstance(payload.get('forecasts'),list):raise ValueError('schema_version=1 및 forecasts 배열이 필요합니다.')
    asof=valid_day(payload['as_of'])
    if any(valid_day(f['as_of'])>asof for f in payload['forecasts']):raise ValueError('입력 기준일 뒤의 전망이 포함되어 있습니다.')
    with state:
        state.execute('BEGIN IMMEDIATE');previous=all_forecasts(state);validate_forecasts(payload['forecasts'],src,previous)
        before=state.total_changes;stamp=datetime.now().astimezone().isoformat(timespec='seconds')
        for f in payload['forecasts']:
            blob=canonical(f)
            state.execute('INSERT OR IGNORE INTO forecasts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(f['forecast_id'],f['house'],f['country'],f['indicator'],f['reference_period'],f['as_of'],f['unit'],f['scenario'],blob,hashlib.sha256(blob.encode()).hexdigest(),stamp))
        added=state.total_changes-before;digest=hashlib.sha256(canonical(payload).encode()).hexdigest();metadata={k:x for k,x in payload.items() if k!='forecasts'}
        state.execute('INSERT OR IGNORE INTO forecast_imports VALUES(?,?,?,?)',(digest,stamp,len(payload['forecasts']),canonical(metadata)))
    return {'added':added,'unchanged':len(payload['forecasts'])-added,'total_forecasts':len(all_forecasts(state))}


def current_forecasts(forecasts,asof,*,house=None,country=None,indicator=None,strict_before=False):
    valid_day(asof);groups=defaultdict(list)
    for f in forecasts:
        eligible=f['as_of']<asof if strict_before else f['as_of']<=asof
        if eligible and (house is None or f['house']==house) and (country is None or f['country']==country) and (indicator is None or f['indicator']==indicator):
            groups[(f['house'],f['country'],f['indicator'],f['reference_period'],f['unit'],f['scenario'])].append(f)
    result=[]
    for key,history in sorted(groups.items()):
        latest=max(f['as_of'] for f in history);candidates=[f for f in history if f['as_of']==latest];superseded={f['prior_forecast_id'] for f in candidates}
        tips=sorted((f for f in candidates if f['forecast_id'] not in superseded),key=lambda f:f['forecast_id'])
        result.append({'house':key[0],'country':key[1],'indicator':key[2],'reference_period':key[3],'unit':key[4],'scenario':key[5],'conflict':len(tips)>1,'forecasts':tips})
    return result


def current_views(views, asof, *, house=None, country=None, strict_before=False):
    valid_day(asof)
    groups = defaultdict(list)
    for v in views:
        eligible = v['effective_date'] < asof if strict_before else v['effective_date'] <= asof
        if eligible and (house is None or v['house'] == house) and (country is None or v['country'] == country):
            groups[(v['house'],v['country'],v['track'])].append(v)
    result = []
    for key, history in sorted(groups.items()):
        latest = max(v['effective_date'] for v in history)
        candidates = [v for v in history if v['effective_date'] == latest]
        superseded = {v['prior_view_id'] for v in candidates}
        tips = [v for v in candidates if v['view_id'] not in superseded]
        result.append({'house':key[0], 'country':key[1], 'track':key[2], 'conflict':len(tips)>1, 'views':sorted(tips,key=lambda v:v['view_id'])})
    return result


def evidence_data(e, src):
    doc = dict(src.execute('SELECT * FROM documents WHERE doc_id=?', (e['doc_id'],)).fetchone())
    paths = [r['path'] for r in src.execute('SELECT path FROM files WHERE doc_id=? ORDER BY path', (e['doc_id'],))]
    return {**e, 'title':doc['title'], 'published_metadata':doc['published'], 'date_basis':doc['date_basis'], 'first_ingested':doc['first_ingested'], 'paths':paths}


def enrich(v, src):
    return {**v, 'evidence':[evidence_data(e,src) for e in v['evidence']]}


def cell(text):
    return re.sub(r'\s+', ' ', str(text)).replace('|','\\|')


def anchor(v):
    return 'view-' + v['view_id'].lower().replace('.','-')


def file_link(label, path):
    return f'[{cell(label)}](<{str(path).replace(chr(92), "/")}>)'


def view_lines(v, src, *, asof):
    age = (valid_day(asof)-valid_day(v['effective_date'])).days
    lines = [f'<a id="{anchor(v)}"></a>', f'### {TRACKS[v["track"]]} · {v["effective_date"]}', '',
             v['summary'], '', f'- 범위: {SCOPES[v["scope"]]} / 기준일로부터 {age}일 경과 / 검토 초안',
             f'- 변경 확인: {CHANGE[v["change"]]} — {v["change_note"]}']
    if v['assumptions']:
        lines.append('- 원문에 근거한 전제: ' + ' / '.join(v['assumptions']))
    if v['watch']:
        lines.append('- 연결 지표: ' + ', '.join(v['watch']))
    if v['analyst_questions']:
        lines.append('- 지표 발표 때 확인할 질문(우리의 검토 질문): ' + ' / '.join(v['analyst_questions']))
    if v['limitations']:
        lines.append('- 해석 제한: ' + ' / '.join(v['limitations']))
    for e in v['evidence']:
        meta = evidence_data(e,src)
        link = file_link(meta['title'],meta['paths'][0]) if meta['paths'] else cell(meta['title'])
        lines.extend(['', f'근거: {link}, **PDF {e["page"]}쪽** · 원본 ID `{e["doc_id"][:12]}`', '', '> ' + norm(e['quote'])])
    return lines + ['']


def review_queue(src, views, asof):
    used = {e['doc_id'] for v in views if v['effective_date']<=asof for e in v['evidence']}
    last = {h:max((v['effective_date'] for v in views if v['house']==h and v['effective_date']<=asof),default='') for h in HOUSES}
    tags = defaultdict(list)
    for r in src.execute("SELECT doc_id,value FROM tags WHERE kind='country' ORDER BY value"):
        tags[r['doc_id']].append(r['value'])
    queue=[]
    for r in src.execute('SELECT doc_id,house,title,published,date_review,status FROM documents ORDER BY published DESC,doc_id'):
        if r['house'] not in HOUSES or r['doc_id'] in used:
            continue
        if r['published'] and r['published']>asof:
            continue
        reason = 'date_review' if r['date_review'] or not r['published'] else ('recent_unreviewed' if r['published']>=last[r['house']] else 'history_unreviewed')
        queue.append({**dict(r), 'candidate_countries_from_title':tags[r['doc_id']], 'priority':reason, 'note':'제목 태그는 검토 경로 안내용이며 견해 근거가 아님. 글로벌 보고서 본문에 추가 국가가 있을 수 있음.'})
    rank={'date_review':0,'recent_unreviewed':1,'history_unreviewed':2}
    return sorted(queue,key=lambda r:(rank[r['priority']],-(int((r['published'] or '0000-00-00').replace('-',''))),r['doc_id']))


def build_outputs(src, state, output, asof):
    output=Path(output)
    views=all_views(state)
    validate_views(views,src)
    forecasts=all_forecasts(state)
    validate_forecasts(forecasts,src)
    history=[v for v in views if v['effective_date']<=asof]
    groups=current_views(views,asof)
    queue=review_queue(src,views,asof)
    source_counts=Counter({r['house']:r['n'] for r in src.execute("SELECT house,count(*) n FROM documents WHERE status='indexed' GROUP BY house")})
    used={e['doc_id'] for v in history for e in v['evidence']}
    current_count=sum(len(g['views']) for g in groups)
    fg=current_forecasts(forecasts,asof);current_forecast_count=sum(len(g['forecasts']) for g in fg)
    forecast_history=[f for f in forecasts if f['as_of']<=asof]
    summary={'as_of':asof,'indexed_documents':sum(source_counts.values()),'view_source_documents':len(used),'historical_assertions':len(history),'current_assertions':current_count,'historical_forecasts':len(forecast_history),'current_forecasts':current_forecast_count,'evidence_quotes':sum(len(v['evidence']) for v in history)+sum(len(f['evidence']) for f in forecast_history),'draft':True,'scope_note':NOTE,'time_note':TIME_NOTE,'review_queue_documents':len(queue)}
    write_json(output/'summary.json',summary)
    write_json(output/'review_queue.json',queue)
    for house in HOUSES:
        hg=[g for g in groups if g['house']==house]
        enriched=[{**g,'views':[enrich(v,src) for v in g['views']]} for g in hg]
        write_json(output/house/'state.json',{'schema_version':1,'as_of':asof,'house':house,'status':'draft','scope_note':NOTE,'time_note':TIME_NOTE,'current':enriched})
        hh=[v for v in history if v['house']==house]
        write_json(output/house/'history.json',[enrich(v,src) for v in hh])
        hf=[g for g in fg if g['house']==house]
        write_json(output/house/'forecasts.json',[{**g,'forecasts':[enrich(f,src) for f in g['forecasts']]} for g in hf])
        lines=[f'# {house} — 살아있는 리서치 모듈', '',f'자료 기준일: **{asof}** · [전체 비교](../IB_COMPARE.md) · [이력](../CHANGELOG.md)', '',NOTE,'',TIME_NOTE,'',
               f'검색 가능한 원본 {source_counts[house]:,}개 중 {len({e["doc_id"] for v in hh for e in v["evidence"]})}개를 이 모듈의 초기 근거로 검토했습니다. 이력 {len(hh)}건, 현재 견해 {sum(len(g["views"]) for g in hg)}건입니다.', '',
               '새 지표는 아래 전제를 점검하는 입력입니다. 새 지표에 대한 AI 해석은 별도 초안으로 작성하며 IB가 실제 전망을 수정했다는 기록으로 저장하지 않습니다. 새 리포트의 근거를 가져올 때만 IB 견해 이력을 추가합니다.', '']
        for country,name in COUNTRIES.items():
            cg=[g for g in hg if g['country']==country]
            if not cg and country=='GLOBAL':
                continue
            lines += [f'## {name}', '']
            if not cg:
                lines += ['이 국가의 견해 근거를 아직 검토하지 않았습니다.', '']
            elif not any(g['track'] in {'policy.near_term','policy.easing_start'} for g in cg) and country!='GLOBAL':
                lines += ['**정책금리 기본 경로는 미확보입니다.** 아래의 성장·물가·판단 조건을 금리 전망으로 확대 해석하지 않습니다.', '']
            for g in sorted(cg,key=lambda g:(not g['track'].startswith('policy.'),g['track'])):
                if g['conflict']:
                    lines += ['**같은 기준일의 상충 가능성이 있는 견해가 있습니다. 후속 원본 확인 전 하나로 합치지 않습니다.**','']
                for v in g['views']:
                    lines.extend(view_lines(v,src,asof=asof))
        atomic_text(output/house/'MODULE.md','\n'.join(lines))
    compare=['# IB별 국가 비교 — 확인한 최신 견해', '',f'기준일: **{asof}** · [시작 안내](START_HERE.md)', '',NOTE,'',
             '문장에 표시된 전망 시점·조건을 함께 읽어야 합니다. 지표 감시 질문은 IB가 공표한 수치 임계값이 아닙니다. 원문과 전체 쟁점은 하우스 이름의 링크에서 확인할 수 있습니다.', '']
    for country,name in COUNTRIES.items():
        if country=='GLOBAL':continue
        compare += [f'## {name}', '', '| IB | 정책 전망 또는 확보 상태 | 자료 기준일 | 근거 범위 |', '|---|---|---|---|']
        for house in HOUSES:
            cg=[g for g in groups if g['house']==house and g['country']==country]
            policy=sorted((g for g in cg if g['track'] in {'policy.near_term','policy.easing_start'}),key=lambda g:g['track']!='policy.near_term')
            if policy:
                chosen=policy
                text=' / '.join(('⚠ 같은 날짜 복수 견해: ' if g['conflict'] else '')+v['summary'] for g in chosen for v in g['views'])
            else:
                chosen=[g for g in cg if g['track']=='policy.reaction']
                text='금리 경로 미확보. '+(' / '.join(v['summary'] for g in chosen for v in g['views']) if chosen else '다른 쟁점의 검토 내용은 모듈 참조.')
            dates=', '.join(sorted({v['effective_date'] for g in chosen for v in g['views']})) or '—'
            scopes=', '.join(sorted({SCOPES[v['scope']] for g in chosen for v in g['views']})) or '—'
            compare += [f'| [{house}]({house}/MODULE.md) | {cell(text)} | {dates} | {scopes} |']
        compare += ['']
    atomic_text(output/'IB_COMPARE.md','\n'.join(compare))
    forecast_lines=['# IB 수치 전망 — 원문 근거 확인본','',f'기준일: **{asof}** · 모든 수치는 사용자 검토 전 초안입니다. 같은 지표라도 단위와 대상 기간을 반드시 함께 보세요.','',
                    '| IB | 국가 | 지표 | 대상 기간 | 전망 | 시나리오 | 기준일 | 원문 |','|---|---|---|---|---:|---|---|---|']
    enriched_forecasts=[]
    for g in fg:
        for f in g['forecasts']:
            ef=enrich(f,src);enriched_forecasts.append(ef);e=ef['evidence'][0]
            source=file_link(e['title'],e['paths'][0]) if e['paths'] else cell(e['title'])
            conflict='⚠ ' if g['conflict'] else ''
            forecast_lines.append(f'| {f["house"]} | {COUNTRIES[f["country"]]} | {f["indicator"]} | {f["reference_period"]} | {conflict}{f["value"]} {f["unit"]} ({cell(f["qualifier"])}) | {f["scenario"]} | {f["as_of"]} | {source}, PDF {e["page"]}쪽 |')
    write_json(output/'forecasts.json',enriched_forecasts)
    atomic_text(output/'FORECASTS.md','\n'.join(forecast_lines)+'\n')
    changes=['# 원본끼리 대조한 견해 이력', '',NOTE,'','`변경`은 연결된 두 원본의 동일 쟁점을 대조한 결과입니다. 같은 방향을 재확인한 것은 `유지`로 구분합니다. 원문이 자체적으로 언급한 과거 전망 변경은 이전 원본과 대조하지 않았다면 여기에 넣지 않았습니다.','']
    byid={v['view_id']:v for v in history}
    for v in sorted((v for v in history if v['prior_view_id']),key=lambda v:(v['effective_date'],v['view_id']),reverse=True):
        p=byid[v['prior_view_id']]
        changes += [f'## {v["house"]} · {COUNTRIES[v["country"]]} · {TRACKS[v["track"]]} · {CHANGE[v["change"]]}','',f'**{p["effective_date"]} → {v["effective_date"]}**','',f'- 이전: {p["summary"]}',f'- 이후: {v["summary"]}',f'- 비교 설명: {v["change_note"]}']
        for label,item in [('이전',p),('이후',v)]:
            e=evidence_data(item['evidence'][0],src)
            changes.append(f'- {label} 원본: '+(file_link(e['title'],e['paths'][0]) if e['paths'] else e['title'])+f', PDF {e["page"]}쪽')
        changes += ['']
    atomic_text(output/'CHANGELOG.md','\n'.join(changes))
    coverage=['# 분석 범위와 검토 대기', '',f'상태 기준일: {asof}. 원본 검색 DB {sum(source_counts.values()):,}개, 견해 근거로 선별 검토한 원본 {len(used)}개, 견해 이력 {len(history)}건, 페이지 인용 {summary["evidence_quotes"]}개.','',
              '원본 수는 현재 검색 DB 전체 수량입니다. 그중 기준일 이후 문서는 해당 날짜 상태에서 제외합니다. 원본의 일부 페이지를 검토했다고 보고서 전체 의미 분석을 완료한 것은 아닙니다. 아래 대기 목록은 아직 견해 근거로 채택하지 않은 문서 단위 목록으로, 검토한 원본의 남은 페이지는 별도 점검이 필요합니다.','',
              '| IB | 검색 DB 원본 | 선별 근거 원본 | 견해 이력 | 현재 견해 | 미채택 원본 대기 |','|---|---:|---:|---:|---:|---:|']
    for h in HOUSES:
        hv=[v for v in history if v['house']==h]
        coverage.append(f'| {h} | {source_counts[h]} | {len({e["doc_id"] for v in hv for e in v["evidence"]})} | {len(hv)} | {sum(len(g["views"]) for g in groups if g["house"]==h)} | {sum(q["house"]==h for q in queue)} |')
    coverage += ['', '## 해석 제한', '']
    for h in HOUSES:
        for c,name in COUNTRIES.items():
            if c=='GLOBAL':continue
            cg=[g for g in groups if g['house']==h and g['country']==c]
            if not any(g['track'] in {'policy.near_term','policy.easing_start'} for g in cg):
                coverage.append(f'- {h} {name}: 정책금리 경로를 확인한 근거가 아직 없습니다. 다른 쟁점이 있어도 금리 전망으로 추정하지 않습니다.')
    older=[v for g in groups if g['track'].startswith('policy.') for v in g['views'] if (valid_day(asof)-valid_day(v['effective_date'])).days>21]
    if older:
        coverage.append('- 정책 견해 중 기준일로부터 21일 넘게 지난 자료: '+', '.join(f'{v["house"]} {COUNTRIES[v["country"]]} {v["effective_date"]}' for v in older)+'. 경과일은 검토 우선순위용이며 전망이 만료됐다는 뜻은 아닙니다.')
    coverage += ['- 다른 지역/글로벌 보고서의 짧은 요약에 근거한 견해는 각 모듈에 범위를 표시했습니다. 상세한 국가별 원본 보강이 필요합니다.', '- 일부 원본의 표지 날짜·표 숫자·본문 시점 불일치는 해당 견해의 제한에 기록했습니다. 불일치 숫자는 채택하지 않았습니다.', '',TIME_NOTE,'',
                 '## 다음 검토 대상', '', '제목 기반 국가 태그는 라우팅용입니다. 먼저 최신 보고서를 검토하고, 이후 과거 9개월의 전망 전환점을 채우면 됩니다. 전체 목록은 [review_queue.json](review_queue.json)에 있습니다.','', '| IB | 발행일 | 제목 | 우선순위 |','|---|---|---|---|']
    for q in queue[:60]:
        coverage.append(f'| {q["house"]} | {q["published"] or "불명"} | {cell(q["title"])} | {q["priority"]} |')
    atomic_text(output/'COVERAGE.md','\n'.join(coverage)+'\n')
    start=['# 살아있는 IB 리서치 — 여기서 시작','',f'**{asof} 기준 · 5개 IB · 6개 국가와 글로벌 쟁점**','',
           f'원본 {sum(source_counts.values()):,}개를 검색할 수 있고, 그중 {len(used)}개 원본에서 견해 이력 {len(history)}건과 근거 인용 {summary["evidence_quotes"]}개를 연결했습니다. 현재 견해는 {current_count}건입니다.','',NOTE,'',
           '1. [IB별 국가 비교](IB_COMPARE.md): 같은 나라를 각 IB가 어떻게 보는지 비교합니다.',
           f'2. [IB 수치 전망](FORECASTS.md): GDP·물가 등 현재 전망 {current_forecast_count}건을 기간·단위·시나리오별로 봅니다.',
           '3. 모듈: '+ ' · '.join(f'[{h}]({h}/MODULE.md)' for h in HOUSES),
           '4. [원본 대조 이력](CHANGELOG.md): 유지와 변경을 이전 원문까지 추적합니다.',
           '5. [분석 범위·검토 대기](COVERAGE.md): 부족한 지역과 다음에 읽을 보고서를 확인합니다.',
           '6. [실행 및 지표 연결 안내](../../README_LIVING_IB.md): 새 견해 추가, 갱신, 지표 발표 준비 방법입니다.','',
           '## 이 모듈을 사용하는 순서','',
           '지표 발표 → 해당 국가·지표의 기존 견해와 전제 불러오기 → 실제값·컨센서스·수정치 대조 → 어느 전제가 유지되거나 약해졌는지 AI 해석 초안 → 후속 IB 보고서와 대조 → 사용자가 국가 판단을 확정합니다.','',
           '각 하우스 폴더의 `state.json`은 현재 견해, `history.json`은 변경 이력입니다. 과거 원본을 다시 읽을 수 있도록 문서 ID·페이지·인용·파일 경로를 함께 보관합니다. 지표 해석을 요청할 때 필요한 부분만 불러오면 되므로 모든 PDF를 매번 대화에 넣을 필요가 없습니다.','',
           '## 현재 동작 범위','',
           '- 새 파일 적재와 검토 대기 갱신, 검증된 견해 추가, IB 비교 재생성은 명령으로 반복 실행할 수 있습니다.',
           '- 지표 입력 파일을 주면 발표 이전 견해와 확인 질문을 모은 해석 준비 묶음을 생성합니다.',
           '- 새 보고서·지표의 의미 해석은 이 앱에서 근거를 읽고 수행합니다. 외부 모델 API, 실시간 지표 연결, 예약 작업은 아직 연결하지 않았습니다.','']
    atomic_text(output/'START_HERE.md','\n'.join(start))
    return summary


def validate_event(event):
    required={'schema_version','event_id','country','indicator','released_at','reference_period','unit','actual','consensus','previous','revised_previous','source_url','source_label','is_example'}
    if set(event)!=required or event['schema_version']!=1:
        raise ValueError('지표 입력 필드 오류. event_template.json을 사용하세요.')
    if not isinstance(event['event_id'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',event['event_id']):
        raise ValueError('event_id는 영문/숫자/._-만 허용합니다.')
    if event['country'] not in COUNTRIES or not isinstance(event['indicator'],str):
        raise ValueError('지표 국가/식별자 오류')
    indicator=event['indicator']
    expected=DECISIONS.get(indicator)
    if expected and event['country']!=expected:
        raise ValueError('정책 결정 지표와 국가가 일치하지 않습니다.')
    if not expected and indicator not in {'ENERGY_PRICES','GLOBAL_PMI','UST_SUPPLY','JPY_FX','DE_FISCAL'} and not indicator.startswith(event['country']+'_'):
        raise ValueError('지표와 국가가 일치하지 않습니다.')
    special_country={'GLOBAL_PMI':'GLOBAL','UST_SUPPLY':'US','JPY_FX':'JP','DE_FISCAL':'EA'}
    if indicator in special_country and event['country']!=special_country[indicator]:
        raise ValueError('특수 지표와 국가가 일치하지 않습니다.')
    stamp=datetime.fromisoformat(event['released_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('발표 시각에 UTC offset이 필요합니다.')
    if event['unit'] not in EVENT_UNITS:
        raise ValueError('지원하지 않는 단위입니다.')
    if indicator in DECISIONS and event['unit']!='pct_level':
        raise ValueError('정책금리 결정은 금리 수준 pct_level로 입력하세요.')
    if indicator=='US_PAYROLLS' and event['unit'] not in {'thousand_persons','persons'}:
        raise ValueError('고용 인원 단위가 필요합니다.')
    if any(x in indicator for x in ('CPI','PCE','PPI','HICP')) and event['unit'] not in {'pct_mom','pct_yoy','pct_qoq','pct_qoq_annualized'}:
        raise ValueError('물가 증가율의 전월비/전년비/전분기비 단위를 명시하세요.')
    if indicator in {'US_UNEMPLOYMENT','US_PARTICIPATION'} and event['unit']!='pct_level':
        raise ValueError('실업률/참가율은 비율 수준 pct_level로 입력하세요.')
    if indicator=='JPY_FX' and event['unit']!='jpy_per_usd':
        raise ValueError('엔 환율은 USD당 엔 jpy_per_usd로 입력하세요.')
    for k in ('actual','consensus','previous','revised_previous'):
        x=event[k]
        if x is None and k!='actual':continue
        if type(x) not in (int,float) or not math.isfinite(x):
            raise ValueError(f'{k}: 실제 수치가 필요하며 NaN/무한대/문자열은 허용하지 않습니다.')
    for k in ('reference_period','source_label'):
        if not isinstance(event[k],str) or not event[k].strip():
            raise ValueError(f'{k} 누락')
    if not isinstance(event['source_url'],str) or not event['source_url'].startswith(('https://','http://')):
        raise ValueError('지표 출처 URL이 필요합니다.')
    if type(event['is_example']) is not bool:
        raise ValueError('is_example은 bool이어야 합니다.')
    return stamp


def prepare_event(event,src,state,output):
    stamp=validate_event(event)
    release_day=stamp.date().isoformat()
    views=all_views(state)
    validate_views(views,src)
    forecasts=all_forecasts(state);validate_forecasts(forecasts,src)
    relevant=[]
    for g in current_views(views,release_day,strict_before=True):
        if g['country'] not in (event['country'],'GLOBAL') and event['country']!='GLOBAL':continue
        matched=[v for v in g['views'] if event['indicator'] in v['watch']]
        if matched:
            # Preserve all tied views if one is relevant; never hide a conflicting sibling.
            relevant.append({**g,'views':[enrich(v,src) for v in g['views']]})
    known={w for v in views for w in v['watch']}|{f['indicator'] for f in forecasts}
    if event['indicator'] not in known:
        raise ValueError('연결되지 않은 지표 ID입니다. indicators.json에서 선택하세요.')
    excluded=[v['view_id'] for v in views if v['effective_date']>=release_day and (event['country']=='GLOBAL' or v['country'] in (event['country'],'GLOBAL')) and event['indicator'] in v['watch']]
    analysis_prompt=(
        '이 입력을 기준으로 국가별 지표 해석 초안을 작성하세요. actual·consensus·previous·revised_previous의 단위와 기준 기간을 유지하고, '
        'IB별 기존 주장과 전제 중 무엇이 강화/약화/미판정인지 원본 ID·페이지를 달아 설명하세요. '
        '실제 IB의 새 코멘트는 제공되지 않았으므로 모든 새로운 해석을 AI 추론으로 명시하세요. '
        '시장 가격 반응이나 IB가 제시하지 않은 수치 임계값을 만들지 마세요. '
        '가장 최근 후속 IB 보고서가 필요하면 검토 대기로 기록하세요. 서로 충돌하는 견해는 병기하세요. '
        '사용자가 판단을 승인하지 않았으므로 최종 국가 상태와 IB 기록을 덮어쓰지 마세요.'
    )
    packet={'schema_version':1,'status':'prepared_not_interpreted','event':event,
            'surprise_in_input_unit':None if event['consensus'] is None else round(event['actual']-event['consensus'],10),
            'previous_revision_in_input_unit':None if event['previous'] is None or event['revised_previous'] is None else round(event['revised_previous']-event['previous'],10),
            'cutoff_rule':'source_effective_date < release_calendar_date; same-day and later sources excluded',
            'time_limit':TIME_NOTE+' 같은 날 자료를 모두 제외하는 보수적 날짜 필터이며 시각 단위의 과거 이용 가능성 검증을 대신하지 않습니다.',
            'same_day_or_later_excluded':excluded,'house_context':relevant,
            'matching_prior_forecasts':[{**g,'forecasts':[enrich(f,src) for f in g['forecasts']]} for g in current_forecasts(forecasts,release_day,country=event['country'],indicator=event['indicator'],strict_before=True)],
            'houses_without_matching_prior_evidence':[h for h in HOUSES if not any(g['house']==h for g in relevant)],
            'analysis_prompt':analysis_prompt}
    blob=canonical(event)
    digest=hashlib.sha256(blob.encode()).hexdigest()
    old=state.execute('SELECT digest FROM events WHERE event_id=?',(event['event_id'],)).fetchone()
    if old and old['digest']!=digest:
        raise ValueError('동일 event_id 수치 변경은 허용하지 않습니다. 수정 발표는 새 event_id를 사용하세요.')
    with state:
        state.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',(event['event_id'],blob,digest,datetime.now().astimezone().isoformat(timespec='seconds')))
    folder=Path(output)/'events'/event['event_id']
    write_json(folder/'context.json',packet)
    lines=[f'# 지표 해석 준비 — {event["event_id"]}','', '**예시 입력 — 실제 발표 자료가 아닙니다.**' if event['is_example'] else '**해석 준비 완료 · AI 해석은 아직 작성하지 않았습니다.**','',
           f'- 국가/지표: {COUNTRIES[event["country"]]} / {event["indicator"]}',f'- 발표 시각: {event["released_at"]}',f'- 대상 기간: {event["reference_period"]}',f'- 단위: {event["unit"]}',
           f'- 실제값: {event["actual"]} / 컨센서스: {event["consensus"]} / 종전: {event["previous"]} / 수정 종전: {event["revised_previous"]}',
           f'- 출처: [{cell(event["source_label"])}](<{event["source_url"]}>)','',packet['time_limit'],'',
           '## 이 앱에 전달할 해석 요청','',analysis_prompt,'', '## 발표 전에 확인한 IB 근거','']
    for g in relevant:
        lines += [f'## {g["house"]} · {COUNTRIES[g["country"]]}','']
        if g['conflict']:lines += ['**복수 견해 충돌: 하나로 합치지 마세요.**','']
        for v in g['views']:lines += view_lines(v,src,asof=release_day)
    lines += ['## 결과를 작성할 순서','', '1. 발표 사실과 수정치', '2. IB별 전제: 강화 / 약화 / 미판정 및 근거', '3. IB 사이 공통점과 차이', '4. 국가 판단 초안과 후속 확인 조건', '5. 실제 IB 후속 코멘트가 필요한 항목','', '사전 근거가 없는 IB: '+', '.join(packet['houses_without_matching_prior_evidence'])]
    atomic_text(folder/'PREPARE.md','\n'.join(lines)+'\n')
    return {'event_id':event['event_id'],'status':packet['status'],'matched_groups':len(relevant),'output':str(folder)}


def main():
    home=Path(__file__).resolve().parent
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=home/'data/research.sqlite3')
    ap.add_argument('--state',type=Path,default=home/'data/living_ib.sqlite3')
    ap.add_argument('--output',type=Path,default=home/'output/living_ib')
    subs=ap.add_subparsers(dest='command',required=True)
    imp=subs.add_parser('import-views');imp.add_argument('file',type=Path)
    impf=subs.add_parser('import-forecasts');impf.add_argument('file',type=Path)
    for name in ('build','refresh'):
        p=subs.add_parser(name);p.add_argument('--as-of',default=date.today().isoformat())
    ctx=subs.add_parser('context');ctx.add_argument('--house',choices=HOUSES);ctx.add_argument('--country',choices=COUNTRIES);ctx.add_argument('--as-of',default=date.today().isoformat())
    ev=subs.add_parser('prepare-event');ev.add_argument('file',type=Path)
    subs.add_parser('verify')
    args=ap.parse_args()
    if args.command=='refresh':
        if args.source.resolve()!= (home/'data/research.sqlite3').resolve():
            raise ValueError('refresh는 기본 원본 DB에서만 실행합니다. 다른 DB는 build를 사용하세요.')
        subprocess.run([sys.executable,'-X','utf8',str(home/'research_context.py'),'ingest'],cwd=home,check=True)
    src=source_db(args.source);state=state_db(args.state)
    src.execute('BEGIN')  # One consistent source snapshot even if ingestion runs concurrently.
    try:
        if args.command=='import-views':result=import_views(read_json(args.file),src,state)
        elif args.command=='import-forecasts':result=import_forecasts(read_json(args.file),src,state)
        elif args.command in ('build','refresh'):
            result=build_outputs(src,state,args.output,args.as_of)
            write_json(args.output/'indicators.json',sorted({w for v in all_views(state) for w in v['watch']}|{f['indicator'] for f in all_forecasts(state)}))
        elif args.command=='context':
            views=all_views(state);validate_views(views,src)
            groups=current_views(views,args.as_of,house=args.house,country=args.country)
            result={'as_of':args.as_of,'status':'draft','time_note':TIME_NOTE,'current':[{**g,'views':[enrich(v,src) for v in g['views']]} for g in groups]}
        elif args.command=='prepare-event':result=prepare_event(read_json(args.file),src,state,args.output)
        else:
            views=all_views(state);validate_views(views,src)
            forecasts=all_forecasts(state);validate_forecasts(forecasts,src)
            integrity=state.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity!='ok':raise ValueError(integrity)
            for table in ('views','forecasts','events'):
                for row in state.execute(f'SELECT payload,digest FROM {table}'):
                    if hashlib.sha256(row['payload'].encode()).hexdigest()!=row['digest']:
                        raise ValueError(f'{table}: 저장된 내용의 해시 불일치')
            missing=sorted({p for item in views+forecasts for e in item['evidence'] for p in evidence_data(e,src)['paths'] if not Path(p).is_file()})
            if missing:raise ValueError(f'원본 파일을 찾을 수 없습니다: {missing}')
            result={'integrity':integrity,'views':len(views),'forecasts':len(forecasts),'quotes_verified':sum(len(item['evidence']) for item in views+forecasts),'source_files_verified':True}
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        state.close();src.close()


if __name__=='__main__':
    try:main()
    except (ValueError,sqlite3.Error,KeyError,TypeError) as exc:
        print(f'오류: {exc}',file=sys.stderr)
        raise SystemExit(2)
