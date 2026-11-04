import json
from pathlib import Path

B=Path(__file__).resolve().parent
D=json.loads((B.parent/'PCA_Four_Axis/dashboard_data.json').read_text(encoding='utf8'))
GROUPS=['고용','임금','가계소득·저축','실제 소비','소비심리·판매 설문','생산·수주·가동률','설비·기계 투자','비주거 건설','기업경기 설문','주택 건설','주택 거래·수요','주택 재고·심리','수출 실적','수출 수주·기대','신용·혼합 참고']
def classify(s):
    t=s['label'].lower();g=s['previous_group']
    if any(x in t for x in ['credit','loans','mortgage lending','residential and non-residential']):return GROUPS[-1]
    if g=='C_labor':
        if 'personal income' in t or 'saving rate' in t:return GROUPS[2]
        return GROUPS[1] if any(x in t for x in ['earnings','wage','pay:','regular pay','total pay']) else GROUPS[0]
    if g=='C_actual':return GROUPS[5] if 'manufacturers new orders' in t or 'domestic shipments' in t else GROUPS[3]
    if g=='C_sentiment':
        if 'jobs hard' in t:return GROUPS[0]
        if 'pmi' in t or 'ifo' in t:return GROUPS[8]
        return GROUPS[4]
    if g=='I_business':
        if 'nonres' in t or 'non-res' in t:return GROUPS[7]
        if any(x in t for x in ['capital','machinery','machine tools','investment','business oriented','general-purpose','equipment']):return GROUPS[6]
        if any(x in t for x in ['pmi','survey','ifo','diffusion','business','order book']):return GROUPS[8]
        return GROUPS[5]
    if g=='I_housing':
        if 'stocks avg' in t or 'market index' in t:return GROUPS[11]
        if any(x in t for x in ['sales','sold','transactions','enquiries']):return GROUPS[10]
        return GROUPS[9]
    return GROUPS[13] if any(x in t for x in ['survey','pmi','expectations','order book']) else GROUPS[12]
for s in D['indicators']:
    s['heatmap_group']=classify(s)
    s['neutral']=any(x in s['label'].lower() for x in ['saving','quits','separations','stocks avg','filled vacancies']) or s['heatmap_group']==GROUPS[-1]
D['heatmap_groups']=GROUPS
page=(B/'template.html').read_text(encoding='utf8').replace('__DATA__',json.dumps(D,ensure_ascii=False).replace('</','<\\/'))
(B/'index.html').write_text(page,encoding='utf8')
print('Saved',B/'index.html','with',len(D['indicators']),'indicators')
