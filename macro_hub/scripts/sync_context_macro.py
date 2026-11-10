"""Publish the latest Context Macro HTML; never copy research PDFs or databases."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
latest=json.loads((ROOT/'데일리시황/표_업데이트/latest.json').read_text(encoding='utf8'))
source=Path(next(p for p in latest['outputs'] if p.endswith('WECO\\macro_views.html') or p.endswith('WECO/macro_views.html')))
html=source.read_text(encoding='utf8')
def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,str) and (value.startswith('file:') or re.match(r'^[A-Za-z]:[\\/]',value)):
        return ''
    return value
def payload(match):
    data=clean(json.loads(match[2]))
    return match[1]+json.dumps(data,ensure_ascii=False).replace('</','<\\/')+match[3]
html=re.sub(r'(<script id="macroData" type="application/json">)([\s\S]*?)(</script>)',payload,html)
html=html.replace('href="../../../index.html"','href="/econ" target="_top"').replace('href="index.html"','href="/econ" target="_top"')
html=html.replace('지표별 요약·IB 코멘트','경제지표 캘린더')
html=html.replace('</header>','<p style="font-size:12px">원문 제목·자료일·인용은 표시하며, 로컬 원문 PDF는 웹에 게시하지 않습니다.</p></header>')
assert 'file:///' not in html and not re.search(r'[A-Za-z]:\\\\Users',html)
dest=ROOT/'macro_hub/public/embeds/context-macro.html'
dest.write_text(html,encoding='utf8')
print('Context Macro synchronized:',source.name)
