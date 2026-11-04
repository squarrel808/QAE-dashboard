import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

base = Path(r'C:\Users\infomax\Documents\python\QAE\youtube_openai_migration')
source = (base / 'summurizer.py').read_text(encoding='utf-8')
compile(source, 'summurizer.py', 'exec')
tree = ast.parse(source)
functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('summarize_with_openai', 'run_job')], type_ignores=[])
ns = dict(CONFIG={'openai_api_key': 'test-only', 'openai_model': 'gpt-5-nano'}, PANEL_KEYWORDS=[], log=logging.getLogger('test'), requests=SimpleNamespace(post=Mock()), time=SimpleNamespace(sleep=lambda _: None))
exec(compile(functions, 'test', 'exec'), ns)
post = ns['requests'].post
post.return_value = SimpleNamespace(ok=True, json=lambda: {'status': 'completed', 'output': [{'type':'reasoning'}, {'type':'message', 'content':[{'type':'output_text', 'text':'한국어 요약'}]}], 'usage':{}})
assert ns['summarize_with_openai']('title', 'transcript', 'Bloomberg')['summary'] == '한국어 요약'
assert post.call_args.kwargs['json']['model'] == 'gpt-5-nano'
post.return_value = SimpleNamespace(ok=True, json=lambda: {'status':'incomplete', 'output':[]})
assert ns['summarize_with_openai']('title', 'text', 'Bloomberg') is None
post.return_value = SimpleNamespace(ok=False, status_code=429, json=lambda: {'error': {'code':'insufficient_quota'}})
assert ns['summarize_with_openai']('title', 'text', 'Bloomberg') is None
post.return_value = SimpleNamespace(ok=True, json=lambda: {'status':'completed', 'output':[]})
assert ns['summarize_with_openai']('title', 'text', 'Bloomberg') is None
saved = []
ns.update(load_processed=lambda:set(), fetch_recent_videos=lambda **kw:[{'id':'good','title':'good','channel_name':'BBG'}, {'id':'bad','title':'bad','channel_name':'BBG'}], get_transcript=lambda _: 'text', summarize_with_openai=lambda title,*args: {'summary':'ok'} if title=='good' else None, save_processed=lambda ids:saved.append(set(ids)), generate_html_report=lambda results:('report.html','html'))
try:
    ns['run_job']()
    raise AssertionError('Failures must cause a nonzero exit')
except RuntimeError:
    pass
assert saved == [{'good'}], saved
wrapper = (base / 'run_youtube.py').read_text(encoding='utf-8')
compile(wrapper, 'run_youtube.py', 'exec')
w_tree = ast.parse(wrapper)
import re
w_ns = {'re': re}
exec(compile(ast.Module(body=[n for n in w_tree.body if isinstance(n, ast.FunctionDef) and n.name=='parse_child_output'], type_ignores=[]), 'wrapper', 'exec'), w_ns)
r = w_ns['parse_child_output'](['새 영상: 2개', '▶ 처리 중: bad', 'OpenAI 요약 실패: insufficient_quota', '완료! 1개 영상 처리됨'])
assert r[:2] == (2,1) and r[2][0]['status']=='요약실패'
print('PASS: response extraction, quota error, incomplete/empty rejection, failure accounting and no false processed state; syntax valid.')
