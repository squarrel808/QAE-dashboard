import hashlib, json, pathlib, re, shutil
from datetime import datetime

BASE=pathlib.Path('데일리시황/표_업데이트').resolve()
P=pathlib.Path(__file__).resolve().parent
STAGE=P/'staged'
manifest_path=BASE/'latest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
run=pathlib.Path(manifest['review_queue']).parent.parent
weco=run/'WECO'
new=json.loads((STAGE/'macro_views_data.json').read_text(encoding='utf-8'))
old=json.loads((weco/'macro_views_data.json').read_text(encoding='utf-8'))
us=[g for g in new['groups'] if g['house']=='GS' and g['country']=='US' and g['theme']=='inflation']
assert {(g['track'],v['effective_date']) for g in us for v in g['views']}=={('inflation.trend','2026-09-14'),('inflation.outlook','2026-09-16')}
assert sum(len(g['history']) for g in us)==1
assert new['meta']['current_views']==old['meta']['current_views']==60
assert new['meta']['historical_views']==old['meta']['historical_views']==78
assert new['meta']['current_forecasts']==old['meta']['current_forecasts']+1==11
assert len([g for g in old['groups'] if g['house']!='GS' or g['country']!='US'])==len([g for g in new['groups'] if g['house']!='GS' or g['country']!='US'])
payload_path=weco/'dashboard_data.json'
dashboard=json.loads(payload_path.read_text(encoding='utf-8'))
assert dashboard['meta']['macro_views']['view_payload_sha256']==old['meta']['view_payload_sha256']
assert dashboard['meta']['event_count']==247 and dashboard['meta']['reported']==194
dashboard['meta']['macro_views']=new['meta']
encoded=json.dumps(dashboard,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')
indicator=(weco/'index.html').read_text(encoding='utf-8')
indicator,count=re.subn(r'(<script id="data" type="application/json">).*?(</script>)',lambda m:m[1]+encoded+m[2],indicator,count=1,flags=re.S)
assert count==1
macro=(STAGE/'macro_views.html').read_text(encoding='utf-8')
macro=re.sub(r'href="[^"]*">← INDEX 대시보드','href="../../../index.html">← INDEX 대시보드',macro)
macro=macro.replace('<h1>','<a href="../index.html">실행별 INDEX</a><h1>',1)
assert '__MACRO_VIEW_DATA__' not in macro
files=[weco/'macro_views.html',weco/'macro_views_data.json',weco/'dashboard_data.json',weco/'index.html',manifest_path,run/'manifest.json',BASE/'index.html',run/'index.html']
backup=P/'before_publish';backup.mkdir(exist_ok=True)
for f in files:
    dest=backup/f.relative_to(BASE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
stamp=datetime.now().astimezone().isoformat(timespec='seconds')
try:
    (weco/'macro_views.html').write_text(macro,encoding='utf-8')
    shutil.copy2(STAGE/'macro_views_data.json',weco/'macro_views_data.json')
    payload_path.write_text(encoded,encoding='utf-8')
    (weco/'index.html').write_text(indicator,encoding='utf-8')
    manifest['weco']['macro_views']=new['meta']
    manifest['macro_views_updated_at']=stamp
    for f in (manifest_path,run/'manifest.json'):
        f.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for f in (BASE/'index.html',run/'index.html'):
        text=f.read_text(encoding='utf-8')
        text=text.replace('저장 뷰 58건 · 저장 뷰 최신 기준일 2026-09-08','저장 뷰 60건 · 저장 뷰 최신 기준일 2026-09-16')
        if 'GS 미국 물가 뷰:' not in text:
            text=text.replace('<h2>이번에 읽은 원본</h2>','<p>GS 미국 물가 뷰: 9월 11일·14일·16일 원문을 대조해 근원 PCE 추정 변경과 물가 추세 판단을 반영했습니다. 사용자 검토 전 초안입니다.</p><h2>이번에 읽은 원본</h2>',1)
        f.write_text(text,encoding='utf-8')
    assert json.loads((weco/'macro_views_data.json').read_text(encoding='utf-8'))['meta']==manifest['weco']['macro_views']
    assert json.loads((weco/'dashboard_data.json').read_text(encoding='utf-8'))['meta']['macro_views']==manifest['weco']['macro_views']
    assert len(json.loads((weco/'review_queue.json').read_text(encoding='utf-8'))['events'])==63
except Exception:
    for f in files:shutil.copy2(backup/f.relative_to(BASE),f)
    raise
print(json.dumps({'gs_us_inflation_current_views':2,'prior_views':1,'total_current_views':60,'published':str(BASE/'index.html')},ensure_ascii=False))
