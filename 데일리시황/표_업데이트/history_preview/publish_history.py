import hashlib, json, pathlib, re, shutil
from datetime import datetime

BASE=pathlib.Path(__file__).resolve().parents[1]
ROOT=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
STAGE=pathlib.Path(__file__).resolve().parent/'WECO'
manifest_path=BASE/'latest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
run=pathlib.Path(manifest['review_queue']).parent.parent
weco=run/'WECO'
book=pathlib.Path(manifest['inputs']['weco']['path'])
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(book)==manifest['inputs']['weco']['sha256']
data=json.loads((STAGE/'dashboard_data.json').read_text(encoding='utf-8'))
old=json.loads((weco/'dashboard_data.json').read_text(encoding='utf-8'))
latest={e['id']:e for e in old['events'] if e.get('record_origin')!='history'}
current=[e for e in data['events'] if e['record_origin']=='current']
archived=[e for e in data['events'] if e['record_origin']=='history']
assert len(current)==len(latest)==116 and len(archived)==131
assert len(data['events'])==247 and len({e['id'] for e in data['events']})==247
assert len([e for e in data['events'] if e['actual'] is not None])==194
assert all(e['actual'] is not None for e in archived)
assert all(all(e.get(k)==latest[e['id']].get(k) for k in ('survey','actual','prior','revised','scale','currency','unit')) for e in current)
assert all(e['commentary'] is None or e['commentary']['snapshot']=={k:e.get(k) for k in ('survey','actual','prior','revised','scale','currency','unit')} for e in data['events'])
assert any(e['date']=='2026-09-09' for e in archived)
assert data['meta']['macro_views']['view_payload_sha256']==manifest['weco']['macro_views']['view_payload_sha256']
assert data['meta']['commentary_needs_recheck']==0
assert 'macro_views.html' in (STAGE/'index.html').read_text(encoding='utf-8')
assert 'index.html' in (STAGE/'macro_views.html').read_text(encoding='utf-8')
assert len(json.loads((weco/'review_queue.json').read_text(encoding='utf-8'))['events'])==63
stamp=datetime.now().astimezone().isoformat(timespec='seconds')
note=f'WECO 누적 실제값 194건 (최신 원본 63건, 보존한 과거 기록 131건) · 2026-09-03~2026-09-17. 최신 원본과 같은 지표는 최신 수치를 우선합니다.'
indicator=(STAGE/'index.html').read_text(encoding='utf-8')
indicator=indicator.replace('<main>','<main><p class="foot">'+note+'</p><nav><a href="../../../index.html">메인 INDEX</a> · <a href="../index.html">실행별 INDEX</a></nav>',1)
(STAGE/'index.html').write_text(indicator,encoding='utf-8')
macro=(STAGE/'macro_views.html').read_text(encoding='utf-8')
macro=re.sub(r'href="[^"]*">← INDEX 대시보드','href="../../../index.html">← INDEX 대시보드',macro)
macro=macro.replace('<h1>','<a href="../index.html">실행별 INDEX</a><h1>',1)
(STAGE/'macro_views.html').write_text(macro,encoding='utf-8')
paths=[weco/name for name in ('index.html','dashboard_data.json','macro_views.html','macro_views_data.json','validation.json')]+[BASE/'index.html',run/'index.html',manifest_path,run/'manifest.json']
backup=pathlib.Path(__file__).resolve().parent/'before_publish'
for path in paths:
    if path.exists():
        dest=backup/path.relative_to(BASE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
try:
    for name in ('index.html','dashboard_data.json','macro_views.html','macro_views_data.json','validation.json'):
        shutil.copy2(STAGE/name,weco/name)
    for path in (BASE/'index.html',run/'index.html'):
        html=path.read_text(encoding='utf-8')
        html=re.sub(r'WECO 실제값 수록 \d+건','WECO 누적 실제값 194건 (최신 원본 63건)',html)
        html=re.sub(r'경제지표 \d+개에 핵심 요약과 해석을 작성했습니다\. IB 원문 요약·비교 코멘트 \d+건을 함께 표시하며, 긴 원문과 검색 후보는 접어 두었습니다\. IB 요약과 AI 해석 초안은 구분해서 표시합니다\.', '누적 경제지표 152개에 핵심 요약과 해석을 표시합니다. IB 원문 요약·비교 코멘트 186건을 연결했습니다. 과거 기록은 기존 수치와 검토 당시 근거를 유지합니다.',html)
        html=html.replace('<h2>이번에 읽은 원본</h2>','<p>'+note+'</p><h2>이번에 읽은 원본</h2>',1)
        path.write_text(html,encoding='utf-8')
    manifest['weco']=data['meta']
    manifest['weco_refreshed_at']=stamp
    manifest['weco_history']={'enabled':True,'archive':str(ROOT/'ecocal_dashboard/indicator_history.json'),'history_events':131,'published_at':stamp}
    for path in (manifest_path,run/'manifest.json'):
        path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    assert digest(STAGE/'dashboard_data.json')==digest(weco/'dashboard_data.json')
except Exception:
    for path in paths:
        saved=backup/path.relative_to(BASE)
        if saved.exists():shutil.copy2(saved,path)
    raise
print(json.dumps({'published':str(BASE/'index.html'),'total_reported':194,'latest_calendar_reported':63,'history':131,'validation':'passed'},ensure_ascii=False))
