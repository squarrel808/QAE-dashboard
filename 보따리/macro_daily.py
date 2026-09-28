"""One-shot daily macro collection; this script never registers a scheduled task.

Uses Botari's Chrome-then-collector workflow, with macro's separate port 9223
and saved login profile. Existing Botari port 9222/processes are never stopped.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack
from datetime import date, datetime, timedelta
from pathlib import Path

MACRO_DIR = Path(__file__).resolve().parents[1] / '데일리시황' / 'Context' / '_macro'
sys.path.insert(0, str(MACRO_DIR))
import macro_bulk_downloader as m
from run_macro_separate_chrome import PORT, PROFILE

STATE_DIR = MACRO_DIR / '.collector'
OUTPUT = MACRO_DIR / 'outdated'
LOG = logging.getLogger('macro_daily')


class DailyStop(RuntimeError):
    def __init__(self, status, reason, code):
        super().__init__(reason)
        self.status, self.code = status, code


def check_space(state_dir, output, min_free_gib):
    volumes = []
    for target in (state_dir, output):
        existing = Path(target)
        while not existing.exists():
            existing = existing.parent
        free = shutil.disk_usage(existing).free
        volumes.append({'path': str(target), 'free_bytes': free})
        if free < min_free_gib * 1024**3:
            raise DailyStop('stopped_low_disk_space',
                            f'Free space below {min_free_gib:g} GiB at {target}', 4)
    return {'checked': datetime.now(m.KST).isoformat(), 'minimum_free_gib': min_free_gib,
            'volumes': volumes}


def lock_busy(folder):
    # Do not create files in --check mode. Existing locks use the same OS lock as
    # the collector. The real launch rechecks under an exclusively held lock.
    lock_file = Path(folder) / 'collector.lock'
    if not lock_file.exists():
        return False
    with lock_file.open('r+b') as stream:
        stream.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(stream, fcntl.LOCK_UN)
    return False


def build_command(args, run_id, start, end):
    return [sys.executable, '-u', str(MACRO_DIR / 'run_macro_separate_chrome.py'),
            '--mode', 'daily', '--start', str(start), '--end', str(end),
            '--lookback-days', str(args.lookback_days), '--houses', *args.houses,
            '--run-id', run_id, '--state-dir', str(args.state_dir), '--output', str(args.output),
            '--retries', '2', '--pdf-timeout', '45', '--delay', '0.7']


def stop_owned_worker(worker):
    """Only stop the child tree launched by this daily invocation, not Chrome."""
    if worker.poll() is not None:
        return
    if sys.platform == 'win32':
        result = subprocess.run(['taskkill', '/PID', str(worker.pid), '/T', '/F'],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode and worker.poll() is None:
            raise RuntimeError(f'Could not stop owned collector tree PID {worker.pid}.')
    else:
        worker.terminate()
    worker.wait(timeout=20)


def run_daily(args):
    started_at = datetime.now(m.KST)
    end = args.end or (started_at.date() - timedelta(days=1))
    start = end - timedelta(days=args.lookback_days - 1)
    run_id = started_at.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    state_dir, output = args.state_dir.resolve(), args.output.resolve()
    args.state_dir, args.output = state_dir, output
    day = started_at.strftime('%Y-%m-%d')
    log_dir = state_dir / 'logs' / 'daily' / day
    daily_json = log_dir / f'daily_{run_id}.json'
    console_log = log_dir / f'daily_{run_id}.console.log'
    collector_log = state_dir / 'logs' / day / f'run_{run_id}.log'
    collector_json = state_dir / 'logs' / day / f'run_{run_id}.json'
    report = {'run_id': run_id, 'mode': 'daily', 'start': str(start), 'end': str(end),
              'houses': args.houses, 'port': PORT, 'profile': str(PROFILE), 'output': str(output),
              'started': started_at.isoformat(), 'status': 'starting',
              'scheduled': False, 'collector_log': str(collector_log),
              'collector_report': str(collector_json), 'console_log': str(console_log)}

    if args.check:
        try:
            report['disk_space'] = check_space(state_dir, output, args.min_free_gib)
            busy = lock_busy(state_dir / 'campaign-control') or lock_busy(state_dir)
            report['status'] = 'blocked_by_active_collection' if busy else 'ready_to_launch'
            code = 3 if busy else 0
            if importlib.util.find_spec('playwright') is None:
                report.update(status='missing_dependency', reason='Playwright is not installed.')
                code = 5
        except DailyStop as exc:
            report.update(status=exc.status, reason=str(exc))
            code = exc.code
        except Exception as exc:
            report.update(status='check_error', reason=f'{type(exc).__name__}: {exc}')
            code = 5
        report['check_only'] = True
        report['note'] = 'Snapshot only; real launch rechecks locks. No Chrome, download, login check, or scheduled task was started.'
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code

    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', force=True,
                        handlers=[logging.StreamHandler(), logging.FileHandler(
                            log_dir / f'daily_{run_id}.log', encoding='utf-8')])

    owns_campaign_lock = False
    lock_lifetime = ExitStack()

    def save():
        report['updated'] = datetime.now(m.KST).isoformat()
        m.atomic_write_json(daily_json, report)
        # A refused overlapping invocation must not replace an active daily's
        # latest snapshot or race on its atomic-write temporary file.
        if owns_campaign_lock:
            m.atomic_write_json(state_dir / 'logs' / 'latest_daily.json', report)

    worker = None
    code = 5
    try:
        save()
        with ExitStack() as held:
            try:
                # Keep the campaign lock for the entire child lifetime so a
                # queued historical supervisor or second daily cannot overlap.
                held.enter_context(m.run_lock(state_dir / 'campaign-control'))
                with m.run_lock(state_dir):
                    pass
                # Keep ownership through the final status write, including
                # exception paths handled below, before allowing the next run.
                lock_lifetime = held.pop_all()
                owns_campaign_lock = True
            except (RuntimeError, BlockingIOError) as exc:
                raise DailyStop('blocked_by_active_collection',
                                'A bulk campaign or another collector is active. Daily was not started.', 3) from exc
            report['disk_space'] = check_space(state_dir, output, args.min_free_gib)
            command = build_command(args, run_id, start, end)
            LOG.info('Daily %s: %s..%s, %s, Chrome port %s', run_id, start, end, ','.join(args.houses), PORT)
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            with console_log.open('w', encoding='utf-8') as stream:
                worker = subprocess.Popen(command, cwd=MACRO_DIR, stdin=subprocess.DEVNULL,
                                          stdout=stream, stderr=subprocess.STDOUT, env=env)
                try:
                    report.update(status='running', worker_pid=worker.pid)
                    save()
                    launched = last_activity = time.monotonic()
                    previous_activity = None
                    while worker.poll() is None:
                        now = time.monotonic()
                        report['disk_space'] = check_space(state_dir, output, args.min_free_gib)
                        activity = tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None
                                         for p in (console_log, collector_log))
                        if activity != previous_activity:
                            previous_activity, last_activity = activity, now
                        if now - launched >= args.timeout_minutes * 60:
                            raise DailyStop('stopped_time_limit', 'Daily maximum runtime exceeded.', 6)
                        if now - last_activity >= args.stall_minutes * 60:
                            raise DailyStop('stopped_no_progress', 'No collector log activity within the allowed interval.', 6)
                        save()
                        time.sleep(5)
                finally:
                    # Also covers Ctrl+C and failures writing the first PID checkpoint.
                    stop_owned_worker(worker)
            report['collector_exit_code'] = worker.returncode
            if collector_json.exists():
                result = json.loads(collector_json.read_text(encoding='utf-8'))
                report['collector_result'] = result
                complete = (worker.returncode == 0 and result.get('run_id') == run_id
                            and result.get('mode') == 'daily' and result.get('finished')
                            and result.get('start') == str(start) and result.get('end') == str(end)
                            and set(result.get('houses', {})) == set(args.houses)
                            and all(h.get('status') == 'complete' for h in result['houses'].values()))
                code = 0 if complete else 2
                report['status'] = 'complete' if complete else 'incomplete'
            else:
                code = 5
                report.update(status='startup_or_collector_error', reason='Final collector summary is missing; see console log.')
    except DailyStop as exc:
        code = exc.code
        report.update(status=exc.status, reason=str(exc))
        LOG.warning('%s', exc)
    except KeyboardInterrupt:
        code = 130
        report.update(status='interrupted', reason='Daily was interrupted; no further collection will start.')
    except Exception as exc:
        code = 5
        report.update(status='error', reason=f'{type(exc).__name__}: {exc}')
        LOG.exception('Daily failed')
    finally:
        try:
            report.update(finished=datetime.now(m.KST).isoformat(), exit_code=code)
            save()
            LOG.info('Daily finished: %s (exit %s); %s', report['status'], code, daily_json)
        finally:
            lock_lifetime.close()
    return code


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--check', action='store_true', help='Check configuration, space and busy state; no collection or browser startup')
    parser.add_argument('--lookback-days', type=int, default=1, help='Inclusive days ending at --end (default 1, max 31)')
    parser.add_argument('--end', type=date.fromisoformat, help='Default: yesterday in Korea')
    parser.add_argument('--houses', nargs='+', choices=m.HOUSES, default=['BofA','JPM','GS','Citi','HSBC'])
    parser.add_argument('--min-free-gib', type=float, default=5)
    parser.add_argument('--timeout-minutes', type=float, default=120)
    parser.add_argument('--stall-minutes', type=float, default=15)
    args = parser.parse_args(argv)
    if (not 1 <= args.lookback_days <= 31 or not args.min_free_gib >= 5
            or not 0 < args.stall_minutes <= args.timeout_minutes <= 1440):
        parser.error('Require 1..31 lookback days, at least 5 GiB reserve, and 0 < stall <= timeout <= 1440 minutes.')
    args.houses = list(dict.fromkeys(args.houses))
    args.state_dir, args.output = STATE_DIR, OUTPUT
    return args


if __name__ == '__main__':
    raise SystemExit(run_daily(parse_args()))
