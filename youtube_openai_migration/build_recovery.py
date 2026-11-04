import html
import json
import re
from pathlib import Path
from html.parser import HTMLParser

BASE = Path(__file__).resolve().parent
DATA = BASE / 'chat_data'
OUT = BASE / 'recovered_reports'
OUT.mkdir(exist_ok=True)
summaries = json.loads((DATA / 'summaries.json').read_text(encoding='utf-8'))
summaries.update(json.loads((DATA / 'summaries_remaining.json').read_text(encoding='utf-8')))
manifest = json.loads((DATA / 'recovery_manifest.json').read_text(encoding='utf-8'))

def render(text):
    blocks = []
    for line in text.splitlines():
        line = html.escape(line)
        if line.startswith('### '): blocks.append('<h3>' + line[4:] + '</h3>')
        elif line.startswith('## '): blocks.append('<h3>' + line[3:] + '</h3>')
        elif line.startswith('- '): blocks.append('<p>• ' + line[2:] + '</p>')
        elif line: blocks.append('<p>' + line + '</p>')
        else: blocks.append('<br>')
    return '\n'.join(blocks)

outputs = []
for date in sorted({v['report_date'] for v in manifest}):
    videos = [v for v in manifest if v['report_date'] == date]
    original = Path(videos[0]['source_report'])
    source = original.read_text(encoding='utf-8')
    position = iter(videos)
    def replace(match):
        video = next(position)
        return '<div class="summary">' + render(summaries[video['id']]) + '</div>'
    result, count = re.subn(r'<div class="summary">.*?</div>', replace, source, flags=re.S)
    assert count == len(videos)
    result = result.replace('Claude AI 번역 요약', 'Codex 대화에서 직접 재작성 · 2026-10-06 복구')
    notice = '전체 자막 기반 복구 완료' if date != '2026-10-04' else '부분 요약 · 전체 자막 재수집 대기'
    result = result.replace('<div class="cards-container">', f'<p style="text-align:center;color:#e8d44d;margin:20px">{notice}</p><div class="cards-container">')
    assert '요약 서비스 실패' not in result
    assert result.count('<div class="summary">') == len(videos)
    HTMLParser().feed(result)
    target = OUT / date / original.name
    target.parent.mkdir(exist_ok=True)
    target.write_text(result, encoding='utf-8')
    outputs.append({'staged':str(target), 'target':str(original), 'videos':len(videos), 'status':notice})
(OUT / 'publish_manifest.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(outputs,ensure_ascii=False,indent=2))
