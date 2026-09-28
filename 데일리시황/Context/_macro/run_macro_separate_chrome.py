"""Run macro collection in its own Chrome, isolated from Botari and work Chrome.

Examples:
  python run_macro_separate_chrome.py --check
  python run_macro_separate_chrome.py --months 3
  python run_macro_separate_chrome.py --mode login --houses HSBC
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.parse import urlsplit
from datetime import datetime

PROFILE = Path(__file__).resolve().parent / '.collector' / 'chrome-profile'
PORT = 9223
CDP = f"http://127.0.0.1:{PORT}"


def powershell(source):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", source],
        capture_output=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError("Could not verify/start dedicated Chrome: " + result.stderr.strip()[:250])
    return result.stdout.strip()


def dedicated_profile(commandline):
    match = re.search(r'--user-data-dir(?:=|\s+)(?:"([^"]+)"|(\S+))', commandline or "", re.I)
    if not match:
        return False
    return os.path.normcase(os.path.normpath(match[1] or match[2])) == os.path.normcase(str(PROFILE))


def verify_owner():
    # Inspect only the listener on the explicitly specified local automation port.
    source = f"""
    $ErrorActionPreference='Stop'
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
    $macroListeners=@(Get-NetTCPConnection -State Listen -LocalPort {PORT} -ErrorAction SilentlyContinue)
    if ($macroListeners.Count -eq 0) {{ Write-Output '[]'; exit 0 }}
    $macroOwners=@($macroListeners | ForEach-Object {{
      Get-CimInstance Win32_Process -Filter ('ProcessId=' + $_.OwningProcess)
    }} | Select-Object -Unique ProcessId,ExecutablePath,CommandLine)
    ConvertTo-Json -InputObject $macroOwners -Compress
    """
    owners = json.loads(powershell(source).lstrip("\ufeff"))
    if not owners:
        return False
    if len(owners) != 1 or not dedicated_profile(owners[0].get("CommandLine")):
        raise RuntimeError(f"Port {PORT} is not verified as {PROFILE}. Refusing to touch that browser.")
    executable = owners[0].get("ExecutablePath") or ""
    if Path(executable).name.lower() != "chrome.exe":
        raise RuntimeError(f"Port {PORT} does not belong to verified Chrome.")
    return True


def ensure_chrome():
    if not verify_owner():
        candidates = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        ]
        chrome = next((p for p in candidates if p.is_file()), None)
        if not chrome:
            raise RuntimeError("Chrome is not installed in the expected location.")
        PROFILE.mkdir(parents=True, exist_ok=True)
        quoted = str(chrome).replace("'", "''")
        profile_quoted = str(PROFILE).replace("'", "''")
        powershell(
            f"Start-Process -FilePath '{quoted}' -ArgumentList @(" 
            f"'--remote-debugging-port={PORT}','--remote-debugging-address=127.0.0.1',"
            f"'--user-data-dir=\"{profile_quoted}\"','--no-first-run','about:blank') -WindowStyle Hidden"
        )
    for _ in range(20):
        try:
            with urlopen(CDP + "/json/version", timeout=2) as response:
                info = json.load(response)
            if info.get("webSocketDebuggerUrl") and verify_owner():
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise RuntimeError("Dedicated Chrome did not become ready. Work Chrome was not used as a fallback.")


def run_collector(command, minimize=True):
    # Only the collector attaches Playwright to this Chrome. Two independent
    # clients can both auto-dismiss one JavaScript dialog and race the driver.
    # Window management belongs to the collector's single client as well.
    child_command = list(command)
    if minimize and '--minimize-window' not in child_command:
        child_command.append('--minimize-window')
    worker = subprocess.Popen(child_command, cwd=Path(__file__).resolve().parent)
    try:
        return worker.wait()
    except KeyboardInterrupt:
        # The console interrupt also reaches the child; first allow it to save
        # its resume state. Bound every cleanup wait if its driver is broken.
        try:
            worker.wait(timeout=15)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            if worker.poll() is None:
                print('Collector did not stop promptly; stopping only its owned process tree.',
                      file=sys.stderr, flush=True)
                try:
                    if sys.platform == 'win32':
                        subprocess.run(['taskkill', '/PID', str(worker.pid), '/T', '/F'],
                                       capture_output=True, timeout=15,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    else:
                        worker.terminate()
                except (OSError, subprocess.TimeoutExpired):
                    pass
                try:
                    worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
        return 130


def check_sites(houses):
    """Check visible report lists without downloading or exporting login secrets."""
    from playwright.sync_api import sync_playwright
    from macro_bulk_downloader import START_URLS, KST, atomic_write_json
    selectors = {
        'HSBC': '#allReportsTable .reportTableRow',
        'GS': 'a[href*="/content/research/en/reports/"]',
        'JPM': 'a[href*="/research/content/GPS-"]',
        'Citi': '.article-item-body a[href*="/smartlink/research/"]',
        'BofA': 'a[onclick*="htmlIconClickOnCachedPortlet"]',
    }
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        for house in houses:
            page = context.new_page()
            ready = False
            error = ''
            try:
                page.goto(START_URLS[house], wait_until='domcontentloaded', timeout=30000)
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if any(frame.locator(selectors[house]).count() for frame in page.frames):
                        ready = True
                        break
                    page.wait_for_timeout(500)
            except Exception as exc:
                error = type(exc).__name__
            results[house] = {
                'status': 'report_list_ready' if ready else 'login_or_site_check_needed',
                'title': page.title() if not page.is_closed() else 'Page closed',
                'error': error,
            }
            print(house + ': ' + json.dumps(results[house], ensure_ascii=True), flush=True)
            if ready:
                page.close()
            # Leave authentication pages open in the isolated profile for manual login.
    now = datetime.now(KST)
    artifact = PROFILE.parent / 'logs' / now.strftime('%Y-%m-%d') / f'isolated_login_check_{now:%H%M%S}.json'
    atomic_write_json(artifact, {'checked': now.isoformat(), 'port': PORT, 'profile': str(PROFILE), 'houses': results})
    return 0 if all(x['status'] == 'report_list_ready' for x in results.values()) else 2


def open_login_window(houses=None):
    """Show the isolated macro browser's existing authentication tabs."""
    from playwright.sync_api import sync_playwright
    from macro_bulk_downloader import START_URLS
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        houses = houses or list(START_URLS)
        pages = []
        for house in houses:
            url = START_URLS[house]
            hostname = urlsplit(url).hostname
            page = next((p for p in context.pages if not p.is_closed() and
                         (urlsplit(p.url).hostname == hostname or house.casefold() in p.title().casefold())), None)
            if page is None:
                page = context.new_page()
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                except Exception:
                    pass
            pages.append(page)
        page = pages[0]
        session = context.new_cdp_session(page)
        try:
            window = session.send('Browser.getWindowForTarget')
            session.send('Browser.setWindowBounds', {
                'windowId': window['windowId'], 'bounds': {'windowState': 'normal'},
            })
        finally:
            session.detach()
        page.bring_to_front()
    print(f'Isolated macro login window is ready (port 9223): {", ".join(houses)}. No collection has started.', flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--check", action="store_true", help="Verify dedicated Chrome without collecting")
    parser.add_argument("--check-sites", action="store_true", help="Check isolated profile logins without downloading")
    parser.add_argument("--open-login", action="store_true", help="Show isolated login tabs, then exit without collecting")
    parser.add_argument("--mode", choices=["scan", "backfill", "daily", "login", "status"], default="backfill")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--show-window", action="store_true", help="Do not minimize dedicated Chrome")
    args, extra = parser.parse_known_args(argv)
    if args.months < 1:
        parser.error("--months must be positive")
    if any(arg.split("=")[0] in {"--cdp-url", "--profile-dir", "--headless"} for arg in extra):
        parser.error("This launcher fixes the browser to the isolated macro profile on port 9223; browser overrides are disabled.")
    collector = Path(__file__).resolve().with_name("macro_bulk_downloader.py")
    if not collector.is_file():
        raise RuntimeError("Place this launcher next to macro_bulk_downloader.py.")
    command = [sys.executable, "-u", str(collector), "--mode", args.mode, "--months", str(args.months),
               "--cdp-url", CDP, *extra]
    if args.mode == "status":
        return subprocess.call(command)
    ensure_chrome()
    print(f"Verified: isolated macro Chrome / {PROFILE} / port {PORT}.", flush=True)
    if args.check:
        return 0
    if args.open_login:
        from macro_bulk_downloader import parser as collector_parser
        return open_login_window(collector_parser().parse_args(extra).houses)
    if args.check_sites:
        from macro_bulk_downloader import parser as collector_parser
        return check_sites(collector_parser().parse_args(extra).houses)
    return run_collector(command, minimize=not args.show_window and args.mode != "login")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
