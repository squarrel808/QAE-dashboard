"""Read-only interpretation audit adapter plus explicit start/end monitoring.

No report collection, interpretation, git or deployment is run here.
"""
import argparse
import csv
import importlib.util
import json
import subprocess
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

QAE = Path(__file__).resolve().parents[1]
RUNS = QAE / '데일리시황/표_업데이트/interpretation_runs'
LOGS = QAE / 'logs/ib_interpretation'
JOURNAL = LOGS / 'events.jsonl'


def deployment_status():
    """Read the real Windows task result; use a dated cache if access is denied."""
    cache = LOGS / 'deployment_task_status.json'
    command = """$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
$t=Get-ScheduledTask -TaskName 'QAE대시보드갱신';
$i=$t | Get-ScheduledTaskInfo;
[pscustomobject]@{observed_at=(Get-Date).ToString('o');state=[string]$t.State;enabled=$t.Settings.Enabled;
last_run=$i.LastRunTime.ToString('o');result=[long]$i.LastTaskResult;
next_run=$i.NextRunTime.ToString('o');execute=$t.Actions.Execute;arguments=$t.Actions.Arguments} | ConvertTo-Json -Compress"""
    try:
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                                capture_output=True, timeout=15, creationflags=0x08000000)
        if result.returncode:
            raise ValueError('Task query denied or failed')
        data = json.loads(result.stdout.decode('utf-8-sig'))
        LOGS.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        data['cached'] = False
        return data
    except (OSError, ValueError, subprocess.TimeoutExpired):
        if cache.exists():
            return {**read(cache), 'cached':True}
        return {'unavailable':True}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def append(event):
    LOGS.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')


def scheduler_failures():
    """Catch failures before the model can execute the begin logging hook.

    Read only this automation's first turn. A later manual recovery in the same
    task must not erase the original scheduled failure.
    """
    home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    found = []
    try:
        with sqlite3.connect((home/'sqlite/codex-dev.db').as_uri()+'?mode=ro', uri=True) as db:
            ids = [r[0] for r in db.execute('SELECT thread_id FROM automation_runs WHERE automation_id=?', ('qae-ib-07-20',))]
        with sqlite3.connect((home/'state_5.sqlite').as_uri()+'?mode=ro', uri=True) as db:
            for tid in ids:
                row = db.execute('SELECT rollout_path FROM threads WHERE id=?', (tid,)).fetchone()
                if not row or not Path(row[0]).exists():
                    continue
                with Path(row[0]).open(encoding='utf-8') as f:
                    for line in f:
                        event = json.loads(line)
                        payload = event.get('payload', {})
                        if event.get('type') != 'event_msg' or payload.get('type') != 'task_complete':
                            continue
                        error = payload.get('error')
                        if error:
                            stamp = datetime.fromtimestamp(payload['started_at']).astimezone()
                            message = error.get('message', str(error))
                            if error.get('codex_error_info') == 'usage_limit_exceeded':
                                message = 'Codex 사용량 한도 초과: AI 해석 시작 전 예약 실행 실패. ' + message
                            found.append(dict(run_id=tid+'_scheduled', start_time=stamp.strftime('%Y-%m-%d %H:%M:%S'),
                                end_time=datetime.fromtimestamp(payload['completed_at']).astimezone().strftime('%Y-%m-%d %H:%M:%S'),
                                duration_sec=round(payload.get('duration_ms',0)/1000, 2), monitor_status='FAILED',
                                collect_result='FAILED', send_result='SKIPPED', error=message,
                                execution_origin='scheduled', thread_id=tid, source='Codex task_complete error'))
                        break
    except (sqlite3.Error, OSError, ValueError, KeyError):
        # Inaccessible app state is not proof of success or failure.
        pass
    return found


def project_data(today=None):
    today = today or datetime.now().date()
    runs, details, steps = [], {}, {}
    for path in sorted(RUNS.glob('*/run_record.json')):
        try:
            d = read(path)
            stamp = d.get('completed_at') or d.get('finished_at') or d.get('recorded_at')
            if not stamp:
                stamp = path.parent.name[:8]
                stamp = datetime.strptime(stamp, '%Y%m%d').isoformat()
            dt = datetime.fromisoformat(stamp)
            status = d.get('status', 'unknown')
            good = status.startswith('published')
            rid = path.parent.name
            note = d.get('collection_scope') or d.get('reason') or '; '.join(d.get('limitations', [])[:2])
            count = d.get('updated_summaries', d.get('updated_events', ''))
            if isinstance(count, list):
                count = len(count)
            row = dict(run_id=rid, start_time=dt.strftime('%Y-%m-%d %H:%M:%S'),
                       end_time=dt.strftime('%Y-%m-%d %H:%M:%S'), duration_sec='',
                       collect_result='OK' if good else 'FAILED',
                       monitor_status='PUBLISHED' if good else 'FAILED',
                       send_result='SKIPPED', ok_count=count, total_count=d.get('valid_summaries', ''),
                       trade_date=d.get('actual_values_snapshot_date', ''),
                       error=note, record=str(path), raw_status=status)
            runs.append(row)
            details[rid] = {'ib_review': [f'감사 기록: {path}', f'게시 상태: {status}',
                '전송 SKIPPED = 로컬 게시 전용; Vercel 배포가 아님.',
                '과거 소요시간은 확인된 기록이 없어 미표시.',
                json.dumps(d, ensure_ascii=False, indent=2)]}
            steps[rid] = [dict(step='해석·검증·로컬 게시 (ib_review)', result='OK' if good else 'FAILED', duration_sec='')]
        except (ValueError, OSError) as exc:
            rid = path.parent.name
            runs.append(dict(run_id=rid, start_time=rid[:8], monitor_status='FAILED', collect_result='FAILED',
                             send_result='SKIPPED', error=f'실행 기록 읽기 실패: {exc}'))
    journal = []
    if JOURNAL.exists():
        for line in JOURNAL.read_text(encoding='utf-8').splitlines():
            try:
                journal.append(json.loads(line))
            except ValueError:
                continue
    latest = {}
    for entry in journal:
        latest[entry['run_id']] = entry
    recorded_paths = {r.get('record') for r in runs}
    for rid, e in latest.items():
        if e.get('record') in recorded_paths:
            continue
        stamp = e.get('started_at', e['at'])
        runs.append(dict(run_id=rid, start_time=stamp[:19].replace('T', ' '), end_time=e['at'],
                         monitor_status=e['status'], collect_result='FAILED', send_result='SKIPPED',
                         duration_sec='', error=e.get('message', ''), started_iso=stamp))
    runs.extend(scheduler_failures())
    # Missing evidence is not evidence of a failed run. Preserve that distinction.
    days = {r['start_time'][:10] for r in runs}
    day = datetime(2026, 9, 16).date()
    while day < today:
        if day.isoformat() not in days:
            runs.append(dict(run_id=day.strftime('%Y%m%d')+'_no_record',
                             start_time=day.isoformat()+' 07:20:00', monitor_status='NO_RECORD',
                             collect_result='UNKNOWN', send_result='SKIPPED', duration_sec='',
                             error='해당 날짜 실행·게시 기록 미확인. 실패나 미실행으로 단정하지 않음.'))
        day += timedelta(days=1)
    runs.sort(key=lambda r:r['start_time'], reverse=True)
    return dict(id='qae_ib_interpretation', title='QAE IB 지표 해석 · 07:20',
                next_run='매일 07:20 KST · Codex 예약', next_run_source='예약 설정',
                runs=runs, steps_by_run=steps, failures_by_run={}, logs_by_run=details,
                daily_check=True, schedule_hour=7, schedule_minute=20)


def sync():
    LOGS.mkdir(parents=True, exist_ok=True)
    data = project_data()
    (LOGS/'status.json').write_text(json.dumps({'generated_at':now(), **data}, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['run_id','start_time','end_time','duration_sec','collect_result','monitor_status','send_result',
              'ok_count','total_count','trade_date','error','record']
    with (LOGS/'run_history.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(data['runs'])
    return data


def refresh():
    script = QAE.parent/'scheduler_dashboard.py'
    spec = importlib.util.spec_from_file_location('qae_scheduler', script)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # The legacy collector monitor is unrelated to this monitoring-only request.
    module.refresh_botari = lambda: None
    return module.build()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['begin','finish','fail','sync'])
    p.add_argument('--run-id'); p.add_argument('--record', type=Path)
    p.add_argument('--message', default=''); p.add_argument('--refresh', action='store_true')
    args = p.parse_args(); stamp = now()
    if args.action != 'sync':
        if args.action != 'begin' and not args.run_id:
            p.error('finish/fail require --run-id from begin')
        rid = args.run_id or datetime.now().strftime('%Y%m%d_%H%M%S')+'_codex'
        event = dict(run_id=rid, at=stamp, status={'begin':'RUNNING','finish':'PUBLISHED','fail':'FAILED'}[args.action], message=args.message)
        if args.action == 'begin':
            event['started_at'] = stamp
        elif JOURNAL.exists():
            for line in JOURNAL.read_text(encoding='utf-8').splitlines():
                old = json.loads(line)
                if old['run_id']==rid and old.get('started_at'):
                    event['started_at']=old['started_at']
        if args.action == 'finish':
            if not args.record or not read(args.record).get('status','').startswith('published'):
                p.error('finish requires a successfully published --record')
            event['record'] = str(args.record.resolve())
        append(event); print(rid)
    sync()
    if args.refresh:
        print(refresh())


if __name__ == '__main__':
    main()
