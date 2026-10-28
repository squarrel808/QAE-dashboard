import json
from pathlib import Path
import pandas as pd
BASE=Path(__file__).resolve().parent
def main():
    d=json.loads((BASE/'dashboard_data.json').read_text(encoding='utf8'))
    html=(BASE/'template.html').read_text(encoding='utf8').replace('__DATA__',json.dumps(d,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    html=html.replace('__STACKED_CHART__',(BASE/'stacked_chart.js').read_text(encoding='utf8'))
    html=html.replace('__EXPLORER__',(BASE/'explorer.js').read_text(encoding='utf8'))
    (BASE/'index.html').write_text(html,encoding='utf8')
    table=pd.DataFrame(d['indicators']).rename(columns={'country':'국가','axis':'분류','previous_group':'이전 세부 분류','label':'지표','direction':'경제적 부호','signed_loading':'부호 있는 로딩'})
    (BASE/'classification_signs.html').write_text('<meta charset="utf-8"><style>body{font:14px Malgun Gothic;padding:25px}td,th{padding:8px;border:1px solid #ddd}table{border-collapse:collapse}</style><h1>네 축의 국가별 지표 분류 및 로딩</h1><p>각 축의 지표 전체를 직접 PCA. Momentum은 주 PCA의 차분이며 독립 로딩 없음. 지표 1개인 축은 표준화 단일지표.</p>'+table.to_html(index=False),encoding='utf8')
    rows=[]
    for cc,c in d['countries'].items():
        for mode,v in c['versions'].items():
            i=v['dates'].index(v['latest'])
            for a in d['axes']:rows.append(dict(country=cc,version=mode,axis=a,date=v['latest'],score=v['blocks'][a][i],weight=c['weights'][a],contribution=v['contributions'][a][i]))
    pd.DataFrame(rows).to_csv(BASE/'component_signs.csv',index=False,encoding='utf-8-sig')
    from blackrock_report import build_report
    build_report(d)
    print('Four-axis dashboard ready')
if __name__=='__main__':main()
