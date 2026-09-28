"""Restore saved IB context in a separate local page; never infer new house views."""
from __future__ import annotations
import argparse,collections,hashlib,html,importlib.util,json,os,sqlite3
from contextlib import closing
from datetime import date,datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
THEMES={'growth':'Growth · 성장','inflation':'Inflation · 물가','policy':'통화정책'}
TRACK_THEME={
 'growth.drivers':'growth','growth.risks':'growth','growth.trend':'growth',
 'labor.participation':'growth','labor.trend':'growth','housing.outlook':'growth',
 'consumption.trend':'growth','productivity.trend':'growth',
 'inflation.preview':'inflation','inflation.outlook':'inflation','inflation.trend':'inflation','energy.risks':'inflation',
 'policy.near_term':'policy','policy.easing_start':'policy','policy.reaction':'policy','rates.outlook':'policy'}

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def encode(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')
def module(path):
    spec=importlib.util.spec_from_file_location('macro_views_living_ib',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def build(root,output,asof,requested_at=None,main_href=None):
    root=Path(root);output=Path(output);date.fromisoformat(asof)
    living=module(root/'living_ib.py')
    with closing(living.source_db(root/'data/research.sqlite3')) as src, closing(living.source_db(root/'data/living_ib.sqlite3')) as state:
        stored=living.all_views(state);forecasts=living.all_forecasts(state)
        extra=read(root/'ecocal_dashboard/reviewed_comments.json').get('views',[])
        supplemental=[]
        for original in extra:
            supplemental.append({'change':'uncompared','change_note':'달력에 저장된 보강 견해이며 이전 원본과 직접 대조하지 않았습니다.',
                'review_status':'draft','origin':'assistant_review_of_local_reports',**original})
        dedup={}
        for v in stored+supplemental:
            if v['view_id'] in dedup and living.canonical(v)!=living.canonical(dedup[v['view_id']]):raise ValueError('같은 ID의 다른 거시 뷰')
            dedup[v['view_id']]=v
        combined=list(dedup.values());living.validate_views(combined,src)
        valid=[v for v in combined if v['effective_date']<=asof]
        if any(v['track'] not in TRACK_THEME for v in valid):raise ValueError('거시 뷰의 주제 분류 누락')
        all_by_id={v['view_id']:v for v in valid}
        source_ids=set();page_keys=set()
        def evidence(ref):
            item=living.evidence_data(ref,src)
            available=next((p for p in item['paths'] if Path(p).is_file()),None)
            if not available:raise ValueError('원본 보고서 파일 없음: '+item['doc_id'])
            source_ids.add(item['doc_id']);page_keys.add((item['doc_id'],item['page']))
            item['url']=Path(available).as_uri()+'#page='+str(item['page']);return item
        def enrich(v):
            return {**v,'theme':TRACK_THEME[v['track']],'track_label':living.TRACKS[v['track']],
                'scope_label':living.SCOPES[v['scope']],'change_label':living.CHANGE[v['change']],
                'age_days':(date.fromisoformat(asof)-date.fromisoformat(v['effective_date'])).days,
                'storage_layer':'calendar_supplement' if v['view_id'] in {x['view_id'] for x in supplemental} else 'living_ib',
                'evidence':[evidence(x) for x in v['evidence']]}
        groups=[]
        for group in living.current_views(valid,asof):
            current_ids={v['view_id'] for v in group['views']}
            history=[enrich(v) for v in valid if (v['house'],v['country'],v['track'])==(group['house'],group['country'],group['track']) and v['view_id'] not in current_ids]
            groups.append({**group,'theme':TRACK_THEME[group['track']],'track_label':living.TRACKS[group['track']],
                'views':[enrich(v) for v in group['views']], 'history':sorted(history,key=lambda v:(v['effective_date'],v['view_id']),reverse=True)})
        current_forecasts=[]
        for group in living.current_forecasts(forecasts,asof):
            for f in group['forecasts']:
                living.validate_evidence(f['evidence'],f['house'],date.fromisoformat(f['as_of']),src,f['forecast_id'])
                current_forecasts.append({**f,'conflict':group['conflict'],'evidence':[evidence(x) for x in f['evidence']]})
        current=[v for g in groups for v in g['views']]
        indexed=src.execute('SELECT count(*),max(published) FROM documents WHERE status="indexed"').fetchone()
        meta={'title':'IB 거시 맥락 뷰','as_of':asof,'generated_at':requested_at or datetime.now().astimezone().isoformat(timespec='seconds'),
              'current_views':len(current),'historical_views':len(valid),'prior_views':len(valid)-len(current),
              'source_documents':len(source_ids),'source_pages':len(page_keys),'current_forecasts':len(current_forecasts),
              'latest_view_date':max((v['effective_date'] for v in current),default=None),
              'oldest_current_view_date':min((v['effective_date'] for v in current),default=None),
              'indexed_documents':indexed[0],'latest_indexed_report_date':indexed[1],
              'supplemental_views':sum(v['view_id'] in {x['view_id'] for x in supplemental} for v in current),
              'conflict_groups':sum(g['conflict'] for g in groups),'draft':True,
              'mode':'restored_saved_context_not_new_research',
              'view_payload_sha256':hashlib.sha256(living.canonical(combined).encode()).hexdigest(),
              'note':'저장된 검토 뷰를 복원한 화면입니다. 최근 보고서가 검색 DB에 추가됐더라도 각 하우스의 거시 전망이 새로 검토·갱신됐다는 뜻은 아닙니다.'}
        countries=[{'code':c,'label':label} for c,label in living.COUNTRIES.items() if any(g['country']==c for g in groups)]
        payload={'schema_version':1,'meta':meta,'houses':list(living.HOUSES),'countries':countries,'themes':THEMES,'groups':groups,'forecasts':current_forecasts}
    output.mkdir(parents=True,exist_ok=True)
    main_href=main_href or os.path.relpath(root.parents[2]/'표_업데이트/index.html',output).replace(os.sep,'/')
    encoded=encode(payload)
    template=(HERE/'macro_views.html').read_text(encoding='utf-8')
    result=template.replace('__MACRO_VIEW_DATA__',encoded).replace('__MAIN_HREF__',html.escape(main_href,quote=True))
    (output/'macro_views_data.json').write_text(encoded,encoding='utf-8')
    (output/'macro_views.html').write_text(result,encoding='utf-8')
    return meta

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--as-of',default=date.today().isoformat())
    args=parser.parse_args();print(json.dumps(build(args.root,args.output,args.as_of),ensure_ascii=False,indent=2))
