"""Union reviewed, available monthly reference inputs with the original model.

Concept matches are based on panel text. They do not establish an identical
BlackRock ticker, transformation, sample or loading. This is an expanded user model.
"""
import json
from pathlib import Path
import pandas as pd
B=Path(__file__).resolve().parent
GROUP={'Consumer':'C_actual','Capex':'I_business','Housing':'I_housing','Export':'X'}

def extend(wide,specs,meta,core,write_audit=True):
    rows=json.loads((B/'blackrock_reference.json').read_text(encoding='utf8'))
    baseline=json.loads((B/'pre_blackrock_union.json').read_text(encoding='utf8'))
    original={(r['country'],r['pk']) for r in baseline['indicators']}
    assert original <= {(s['country'],s['pk']) for s in specs.values()}, 'Original input unexpectedly lost'
    # Only newly added inputs face the freshness gate; preserve the original set.
    recent=(pd.Timestamp.now(tz='Asia/Seoul').tz_localize(None)-pd.DateOffset(months=6)).normalize()
    audit=[]
    for row in rows:
        r=dict(row);cc=r['country'];pk=r['pk'];r['original_pk']=pk
        if r.get('fallback_pk'):
            m=meta[pk]
            unusable=m['frequency']!='M' or 'DISC' in m['descriptor'].upper() or pk not in wide or wide[pk].last_valid_index()<recent
            if unusable:
                r['original_frequency']=m['frequency'];r['original_descriptor']=m['descriptor']
                r['pk']=r['fallback_pk'];r['match']='proxy';r['note']=r['fallback_note'];pk=r['pk']
        key=cc+'|'+pk
        r.update(action='excluded',reason='',included_axis='',last='',n=0,descriptor='')
        if not pk:r['reason']='미확인: 조회 가능한 Haver 카탈로그에서 동일 월별 계열을 찾지 못함'
        elif pk not in meta:raise ValueError('Missing verified metadata: '+pk)
        else:
            m=meta[pk];r.update(descriptor=m['descriptor'],frequency=m['frequency'])
            if (cc,pk) in original:
                r.update(action='existing',reason='기존 편입 유지 · 한 번만 사용',included_axis=next(a for a,g in GROUP.items() if g==specs[key]['group']) if specs[key]['group']!='C_sentiment' and specs[key]['group']!='C_labor' else 'Consumer')
            elif row.get('exclude'):r['reason']=row['exclude']
            elif m['frequency']!='M':r['reason']='비월별: '+m['frequency']+' · 월별 보간하지 않음'
            elif 'DISC' in m['descriptor'].upper() or 'SUSP' in m['descriptor'].upper():r['reason']='중단된 계열 · 현행 월별 계열만 신규 편입'
            elif pk not in wide or wide[pk].notna().sum()<36:r['reason']='원자료 36개월 미만'
            elif wide[pk].last_valid_index()<recent:r['reason']='장기 미갱신: 마지막 관측 '+str(wide[pk].last_valid_index())[:10]
            elif key in specs and specs[key]['group'] in ['C_actual','C_sentiment','C_labor','I_business','I_housing','X']:r.update(action='duplicate',reason='다른 참조 항목과 같은 원계열 · 한 번만 사용',included_axis='Consumer' if specs[key]['group'].startswith('C_') else next(a for a,g in GROUP.items() if g==specs[key]['group']))
            else:
                group=GROUP[r['axis']];kind,direction,ambiguous,seasonal=core.classify(m,group)
                if r['kind']!='auto':kind=r['kind']
                direction=r.get('direction',direction)
                # A survey belongs to Consumer sentiment rather than the actual
                # consumption set used to validate the latest headline month.
                if r['axis']=='Consumer' and kind=='rate':group='C_sentiment'
                specs[key]=dict(id=key,country=cc,pk=pk,group=group,label=m['descriptor'],kind=kind,direction=direction,ambiguous=ambiguous or pk=='uk:urshv',seasonal=seasonal,substitution=r['match']=='proxy',note=r['note'],last=str(wide[pk].last_valid_index())[:10],origin='BlackRock reference union',reference=r['reference'])
                r.update(action='added',reason='확인된 현행 월별 계열 편입',included_axis=r['axis'])
            if pk in wide:r.update(last=str(wide[pk].last_valid_index())[:10],n=int(wide[pk].notna().sum()))
        audit.append(r)
    # Same pk across reference panels/categories is one underlying observation.
    for r in audit:
        key=r['country']+'|'+r['pk']
        if key in specs and r['action'] in ['existing','added','duplicate']:
            s=specs[key];r.update(kind=s['kind'],direction=s['direction'])
            s.setdefault('reference_matches',[]).append(r['reference'])
    assert original <= {(s['country'],s['pk']) for s in specs.values() if s['group'] in ['C_actual','C_labor','C_sentiment','I_business','I_housing','X']}
    if write_audit:pd.DataFrame(audit).to_csv(B/'blackrock_coverage.csv',index=False,encoding='utf-8-sig')
    return audit
