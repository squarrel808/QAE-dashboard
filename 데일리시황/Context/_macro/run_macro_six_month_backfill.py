"""One-off: verify recent three months, then collect only the preceding three.

No scheduled task is created. All collection uses the isolated 9223 launcher.
The existing collector lock serializes browser/data access with a prior run.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack
from datetime import date, datetime, timedelta
from pathlib import Path

from macro_bulk_downloader import HOUSES, KST, atomic_write_json, months_before, run_lock
from macro_backfill_audit import audit_house
from run_macro_separate_chrome import PROFILE
from reconcile_interrupted_run import reconcile

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger('macro_six_month_backfill')


class LowDiskSpace(RuntimeError):
    pass


class HouseWatchdog(RuntimeError):
    """A bounded failure of one owned attempt, not a campaign-wide stop."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def progress_snapshot(paths):
    """Only child logs count as activity; supervisor heartbeats do not."""
    activity = []
    for path in paths:
        try:
            stat = path.stat()
            activity.append((stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            activity.append(None)
    return tuple(activity)


def stop_owned_worker(worker):
    """Stop and reap only this invocation's worker tree, or fail closed."""
    if worker.poll() is None:
        if sys.platform == 'win32':
            stopped = subprocess.run(['taskkill', '/PID', str(worker.pid), '/T', '/F'],
                                     capture_output=True, timeout=30,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            if stopped.returncode and worker.poll() is None:
                raise RuntimeError(f'Could not stop owned collector tree PID {worker.pid}.')
        else:
            # Popen creates a new session below, so this cannot target our caller.
            os.killpg(worker.pid, signal.SIGTERM)
        try:
            exit_code = worker.wait(timeout=20)
        except subprocess.TimeoutExpired:
            if sys.platform == 'win32':
                # taskkill already targeted the whole tree; do not pretend a
                # root-only kill proves that descendants have stopped.
                raise RuntimeError(f'Owned collector tree PID {worker.pid} did not exit.')
            os.killpg(worker.pid, signal.SIGKILL)
            exit_code = worker.wait(timeout=20)
    else:
        exit_code = worker.wait(timeout=20)
    if not isinstance(exit_code, int) or worker.poll() is None:
        raise RuntimeError(f'Owned collector PID {worker.pid} has no confirmed exit code.')
    return exit_code


def reconcile_stopped_attempt(args, worker, run_id, reason, attempt):
    """Never rewrite a running invocation or continue while its lock is held."""
    if worker.poll() is None:
        raise RuntimeError('Cannot reconcile an owned collector that is still alive.')
    if not collector_idle(args.state_dir):
        raise RuntimeError('Owned worker exited, but collector lock remains held; refusing to launch another house.')
    run = read_run(args.state_dir, run_id)
    if run and not run.get('finished'):
        day = f'{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]}'
        report = args.state_dir / 'logs' / day / f'run_{run_id}.json'
        log = report.with_suffix('.log')
        if not report.exists() or not log.exists():
            attempt['reconciliation_error'] = 'Matching collector report/log missing; preserved original history.'
            return
        try:
            outcome = reconcile(args.state_dir, run_id, reason, apply=True, confirmed_stopped=True)
            attempt['interruption_audit'] = outcome['audit']
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            # The attempt still has an explicit incomplete campaign record;
            # do not invent historical counts when reconciliation is unsafe.
            attempt['reconciliation_error'] = f'{type(exc).__name__}: {exc}'
            LOG.warning('Could not reconcile stopped run %s: %s', run_id, exc)


def check_disk_space(args, campaign):
    """Keep a reserve on every volume used by this campaign; never delete files."""
    checks = []
    for target in (args.output, args.state_dir):
        existing = target
        while not existing.exists():
            existing = existing.parent
        free = shutil.disk_usage(existing).free
        checks.append({'path': str(target), 'free_bytes': free})
    campaign['disk_space'] = {'minimum_free_gib': args.min_free_gib, 'volumes': checks}
    for check in checks:
        if check['free_bytes'] < args.min_free_gib * 1024**3:
            raise LowDiskSpace(f"Free space below {args.min_free_gib:g} GiB at {check['path']}")


def read_run(state_dir, run_id):
    db_path = state_dir / 'downloads.sqlite3'
    if not db_path.exists():
        return None
    db = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    result = dict(row)
    result['houses'] = json.loads(result.pop('summary') or '{}')
    return result


def collector_idle(state_dir):
    try:
        with run_lock(state_dir):
            return True
    except (RuntimeError, OSError):
        return False


def wait_for_prior_run(state_dir, run_id, checkpoint, poll_seconds=20):
    """Wait on the actual collector lock, not a stale 'running' JSON label."""
    idle_since = None
    while True:
        result = read_run(state_dir, run_id)
        idle = collector_idle(state_dir)
        if idle and result and result.get('finished'):
            return result
        if idle:
            idle_since = idle_since or time.monotonic()
            if time.monotonic() - idle_since >= 40:
                LOG.warning('Prior run %s is no longer active but has no final summary; retry is required.', run_id)
                return result or {'run_id': run_id, 'houses': {}}
        else:
            idle_since = None
        checkpoint()
        time.sleep(poll_seconds)


def execute_house(args, house, start, end, phase, campaign, save):
    check_disk_space(args, campaign)
    run_id = datetime.now(KST).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    command = [sys.executable, '-u', str(ROOT / 'run_macro_separate_chrome.py'),
               '--mode', 'backfill', '--start', start.isoformat(), '--end', end.isoformat(),
               '--houses', house, '--run-id', run_id, '--state-dir', str(args.state_dir),
               '--output', str(args.output), '--retries', '1', '--pdf-timeout', '45', '--delay', '0.7']
    console_log = args.campaign_dir / f'{phase}_{house}_{run_id}.console.log'
    day = f'{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]}'
    collector_log = args.state_dir / 'logs' / day / f'run_{run_id}.log'
    attempt = {'phase': phase, 'house': house, 'start': str(start), 'end': str(end),
               'run_id': run_id, 'started': datetime.now(KST).isoformat(),
               'status': 'running', 'console_log': str(console_log),
               'collector_log': str(collector_log), 'stall_minutes': args.stall_minutes,
               'house_timeout_minutes': args.house_timeout_minutes}
    campaign['attempts'].append(attempt)
    campaign['active'] = {'house': house, 'phase': phase, 'run_id': run_id}
    save()
    LOG.info('%s %s: %s..%s (run %s)', phase, house, start, end, run_id)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    stopped_by_watchdog = None
    with console_log.open('w', encoding='utf-8') as output:
        worker = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output,
                                  stderr=subprocess.STDOUT, env=env,
                                  start_new_session=sys.platform != 'win32')
        try:
            campaign['active']['pid'] = worker.pid
            save()
            launched = last_activity = time.monotonic()
            previous_activity = progress_snapshot((console_log, collector_log))
            while worker.poll() is None:
                check_disk_space(args, campaign)
                now = time.monotonic()
                activity = progress_snapshot((console_log, collector_log))
                if activity != previous_activity:
                    previous_activity, last_activity = activity, now
                    attempt['last_log_activity'] = datetime.now(KST).isoformat()
                attempt['elapsed_seconds'] = round(now - launched, 1)
                attempt['idle_seconds'] = round(now - last_activity, 1)
                if now - launched >= args.house_timeout_minutes * 60:
                    raise HouseWatchdog('stopped_time_limit',
                                        f'House runtime exceeded {args.house_timeout_minutes:g} minutes.')
                if now - last_activity >= args.stall_minutes * 60:
                    raise HouseWatchdog('stopped_no_progress',
                                        f'No console/collector log activity for {args.stall_minutes:g} minutes.')
                save()
                time.sleep(10)
        except BaseException as exc:
            try:
                attempt['exit_code'] = stop_owned_worker(worker)
            except BaseException as cleanup_error:
                attempt.update(status='stop_failed', reason=str(exc),
                               cleanup_error=f'{type(cleanup_error).__name__}: {cleanup_error}')
                save()
                raise
            attempt.update(status='stopped_low_disk_space' if isinstance(exc, LowDiskSpace) else 'interrupted',
                           reason=str(exc), finished=datetime.now(KST).isoformat(),
                           console_log_exists=console_log.exists(), collector_log_exists=collector_log.exists())
            campaign['active'] = None
            if isinstance(exc, HouseWatchdog):
                stopped_by_watchdog = exc
                attempt.update(status='incomplete', stop_kind=exc.kind)
                reconcile_stopped_attempt(args, worker, run_id, str(exc), attempt)
                LOG.warning('%s %s: %s; attempt stopped, retry policy will continue.', phase, house, exc)
            else:
                save()
                raise
        else:
            attempt['exit_code'] = stop_owned_worker(worker)
    attempt.update(finished=datetime.now(KST).isoformat(), console_log_exists=console_log.exists(),
                   collector_log_exists=collector_log.exists())
    run = read_run(args.state_dir, run_id)
    result = (run or {}).get('houses', {}).get(house)
    if stopped_by_watchdog:
        result = dict(result or {}, status='incomplete', reason=str(stopped_by_watchdog),
                      stop_kind=stopped_by_watchdog.kind)
        result.setdefault('counts', {})
    elif not run or not run.get('finished') or not result:
        result = {'status': 'incomplete', 'counts': {},
                  'reason': f"Child exit={attempt['exit_code']}; final run/house summary missing. See {console_log}"}
    elif (attempt['exit_code'] != 0 or not collector_log.exists()) and result.get('status') == 'complete':
        result = dict(result, status='incomplete',
                      reason=f"Child exit={attempt['exit_code']}; collector log present={collector_log.exists()}.")
    attempt['status'] = result['status']
    attempt['result'] = result
    campaign['active'] = None
    save()
    return result, run_id


def run_campaign(args):
    args.state_dir = args.state_dir.resolve()
    args.output = args.output.resolve()
    campaign_id = datetime.now(KST).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    args.campaign_dir = args.state_dir / 'logs' / datetime.now(KST).strftime('%Y-%m-%d') / f'campaign_{campaign_id}'
    args.campaign_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(args.campaign_dir / 'campaign.log', encoding='utf-8')], force=True)
    extension_end = args.trial_start - timedelta(days=1)
    campaign = {'campaign_id': campaign_id, 'started': datetime.now(KST).isoformat(),
                'end': str(args.end), 'trial_start': str(args.trial_start),
                'extension_start': str(args.extension_start), 'extension_end': str(extension_end),
                'status': 'starting', 'port': 9223, 'profile': str(PROFILE),
                'after_run': args.after_run, 'houses': {h: {} for h in args.houses},
                'attempts': [], 'active': None, 'scheduled': False}

    def save():
        campaign['updated'] = datetime.now(KST).isoformat()
        atomic_write_json(args.campaign_dir / 'campaign.json', campaign)
        atomic_write_json(args.state_dir / 'logs' / 'latest_campaign.json', campaign)

    def audit(house, start, end, result, phase, run_id):
        with ExitStack() as held:
            while True:
                try:
                    held.enter_context(run_lock(args.state_dir))
                    break
                except (RuntimeError, BlockingIOError):
                    LOG.info('Waiting for the collector lock before auditing %s.', house)
                    time.sleep(10)
            # Audit bugs must surface as errors, not be mistaken for lock contention.
            review = audit_house(args.state_dir, house, start, end, result)
        path = args.campaign_dir / f'audit_{phase}_{house}_{run_id}.json'
        atomic_write_json(path, review)
        outcome = {'eligible': review['eligible'], 'gate_reasons': review['gate_reasons'],
                   'audit': str(path), 'run_id': run_id, 'result': result}
        campaign['houses'][house][phase] = outcome
        save()
        LOG.info('%s %s verification: %s', phase, house, 'PASS' if review['eligible'] else review['gate_reasons'])
        return review['eligible']

    # Separate campaign lock prevents duplicate supervisors while child collectors use the normal lock.
    with run_lock(args.state_dir / 'campaign-control'):
        save()
        try:
            check_disk_space(args, campaign)
            campaign['status'] = 'waiting_for_current_run'
            save()
            LOG.info('Six-month scope: %s..%s; added interval %s..%s; waiting for run %s.',
                     args.extension_start, args.end, args.extension_start, extension_end, args.after_run or '(none)')
            prior = wait_for_prior_run(args.state_dir, args.after_run, save) if args.after_run else {'houses': {}}
            campaign['status'] = 'verifying_three_months'
            save()
            for house in args.houses:
                result = prior.get('houses', {}).get(house, {'status': 'incomplete', 'counts': {}, 'reason': 'No prior completed trial.'})
                # The joined run must cover the entire trial window before its results can be used.
                if (not prior.get('finished') or prior.get('mode') != 'backfill'
                        or prior.get('start_date', '9999') > str(args.trial_start)
                        or prior.get('end_date', '') < str(args.end)):
                    result = dict(result, status='incomplete', reason='Prior run does not establish completed trial coverage.')
                if house != 'Citi' and result.get('coverage_guard_version') != 1:
                    result = dict(result, status='incomplete',
                                  reason='Recheck with verified pagination endings; older completion labels are not sufficient.')
                passed = audit(house, args.trial_start, args.end, result, 'trial', args.after_run or 'none')
                for _ in range(args.trial_retries):
                    if passed:
                        break
                    result, run_id = execute_house(args, house, args.trial_start, args.end, 'trial', campaign, save)
                    passed = audit(house, args.trial_start, args.end, result, 'trial', run_id)
                if not passed:
                    campaign['houses'][house]['extension'] = {'status': 'held_for_trial_errors',
                                                         'reason': 'Three-month verification has not passed.'}
                    save()
            campaign['status'] = 'collecting_previous_three_months'
            save()
            for house in args.houses:
                if not campaign['houses'][house].get('trial', {}).get('eligible'):
                    continue
                for _ in range(args.extension_retries + 1):
                    result, run_id = execute_house(args, house, args.extension_start, extension_end, 'extension', campaign, save)
                    if audit(house, args.extension_start, extension_end, result, 'extension', run_id):
                        break
            campaign['status'] = ('complete' if all(campaign['houses'][h].get('extension', {}).get('eligible') for h in args.houses)
                                  else 'incomplete')
        except LowDiskSpace as exc:
            campaign['status'] = 'stopped_low_disk_space'
            campaign['error'] = str(exc)
            LOG.warning('%s; no further collection will be launched.', exc)
        except KeyboardInterrupt:
            campaign['status'] = 'interrupted'
            LOG.warning('Campaign interrupted; no further houses will be launched.')
        except BaseException as exc:
            campaign['status'] = 'error'
            campaign['error'] = f'{type(exc).__name__}: {exc}'
            LOG.exception('Campaign failed')
            raise
        finally:
            campaign['finished'] = datetime.now(KST).isoformat()
            save()
    return 0 if campaign['status'] == 'complete' else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--after-run', help='Finish the currently active collector run before proceeding')
    parser.add_argument('--state-dir', type=Path, default=ROOT / '.collector')
    parser.add_argument('--output', type=Path, default=ROOT / 'outdated')
    parser.add_argument('--houses', nargs='+', choices=HOUSES, default=list(HOUSES))
    parser.add_argument('--end', type=date.fromisoformat, default=datetime.now(KST).date())
    parser.add_argument('--trial-start', type=date.fromisoformat, default=date(2026, 6, 8))
    parser.add_argument('--extension-start', type=date.fromisoformat, help='Default: six calendar months before --end; cannot be earlier')
    parser.add_argument('--trial-retries', type=int, default=1, help='Additional full trials for failed houses after the joined run')
    parser.add_argument('--extension-retries', type=int, default=1)
    parser.add_argument('--min-free-gib', type=float, default=5, help='Stop this campaign below this free-space reserve')
    parser.add_argument('--stall-minutes', type=float, default=15, help='Stop one attempt after this many minutes without child log activity')
    parser.add_argument('--house-timeout-minutes', type=float, default=360, help='Maximum runtime of one house attempt')
    args = parser.parse_args(argv)
    args.extension_start = args.extension_start or months_before(args.end, 6)
    if (not months_before(args.end, 6) <= args.extension_start < args.trial_start <= args.end
            or min(args.trial_retries, args.extension_retries) < 0 or not args.min_free_gib >= 5
            or not 0 < args.stall_minutes <= args.house_timeout_minutes <= 1440):
        parser.error('Invalid date/retry limits, disk reserve below 5 GiB, or watchdog limits outside 0 < stall <= house timeout <= 1440 minutes.')
    return run_campaign(args)


if __name__ == '__main__':
    raise SystemExit(main())
