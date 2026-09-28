"""Install the reviewed scheduler integration, preserving a backup."""
import hashlib
import json
import shutil
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
QAE = HERE.parents[1]
target = QAE.parent / 'scheduler_dashboard.py'
baseline = json.loads((HERE/'baseline.json').read_text(encoding='utf-8'))
assert hashlib.sha256(target.read_bytes()).hexdigest() == baseline['source_sha256'], 'Concurrent scheduler edit'
shutil.copy2(target, HERE/'scheduler_dashboard.before.py')
shutil.copy2(target.with_suffix('.html'), HERE/'scheduler_dashboard.before.html')
try:
    shutil.copy2(HERE/'scheduler_dashboard.py', target)
    spec = importlib.util.spec_from_file_location('scheduler', target)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.refresh_botari = lambda: None
    print(m.build())
    assert 'QAE IB 지표 해석' in target.with_suffix('.html').read_text(encoding='utf-8')
except Exception:
    shutil.copy2(HERE/'scheduler_dashboard.before.py', target)
    shutil.copy2(HERE/'scheduler_dashboard.before.html', target.with_suffix('.html'))
    raise
