#!/usr/bin/env python3
"""Five-house macro PDF collector. Python 3.10+, Playwright 1.62+.

Default: scan only. To download: --mode backfill (9 calendar months).
Only original PDFs are saved; a web page is never printed as a substitute.
Site credentials stay in a local Chrome profile. No passwords in this file.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import logging
import re
import sqlite3
import sys
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, unquote

HOUSES = ("HSBC", "GS", "JPM", "Citi", "BofA")
DEFAULT_OUTPUT = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\outdated")
KST = timezone(timedelta(hours=9))
LOG = logging.getLogger("macro_collector")
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}

# The user's exact search definitions. Query strings are search criteria, not login tokens.
START_URLS = {
    "HSBC": "https://www.research.hsbc.com/ibcom/in/reach/servlet/Reach?productid=5",
    "GS": "https://marquee.gs.com/content/research/site/search.html?facets=()&language=%5B%22en%22%5D&page=1&sort=time&limitTo=%5B%22model%22%5D&filter=(disciplines_and_assets%20EQ%20%24%7B(%227c8f0740-d6fe-11df-a204-00118563711b%22)%7D%24%20AND%20totalPages%20IN%20%5B1%2C400%5D)",
    "JPM": "https://markets.jpmorgan.com/jpmm/search?query=YW5hbHl0aWNzPXRydWUmc29ydD1ERVNDRU5ESU5HLU1vc3QgUmVjZW50LVBVQkxJQ0FUSU9OX0RBVEUmZGVmYXVsdERhdGVzPWZhbHNlJmN1c3RvbVF1ZXJpZXM9eyJxdWVyaWVzIjpbeyJkaXNwbGF5TmFtZSI6IkVjb25vbWljcyBDb21tZXRhcnkiLCJ0eXBlTGFiZWwiOiJWaWV3IEFsbCIsInF1ZXJ5Tm9kZSI6eyJvcGVyYXRvciI6Ik9SIiwiY2hpbGRyZW4iOlt7Iml0ZW0iOiJQVUJMSUNBVElPTl9JRCIsIm9wZXJhdG9yIjoiRVFVQUxTIiwidmFsdWVzIjpbIjExMCIsIjkwMDA3NTAiLCI5MDAxMDA1Il19LHsiaXRlbSI6IlBVQkxJQ0FUSU9OX0lEIiwib3BlcmF0b3IiOiJFUVVBTFMiLCJ2YWx1ZXMiOlsiOTAwMDIwOCIsIjI2IiwiOTAwMDczNiIsIjkwMDA3MzciLCI5MDAwNzM4IiwiOTAwMDczOSIsIjE2MzQ4MCIsIjkwMDAyMTUiLCIyODUyMSIsIjkwMDI0OTkiLCI5MDAyNTAxIl19LHsib3BlcmF0b3IiOiJBTkQiLCJjaGlsZHJlbiI6W3siaXRlbSI6IlBVQkxJQ0FUSU9OX0lEIiwib3BlcmF0b3IiOiJOT1RfRVFVQUxTIiwidmFsdWVzIjpbIjkwMDA3MjciLCI0ODciLCI5MDAwNzMwIl19LHsiaXRlbSI6IkRPQ1VNRU5UX1RZUEUiLCJvcGVyYXRvciI6Ik5PVF9FUVVBTFMiLCJ2YWx1ZXMiOlsiVklERU8iLCJBVURJTyJdfSx7Iml0ZW0iOiJQVUJMSUNBVElPTl9JRCIsIm9wZXJhdG9yIjoiTk9UX0VRVUFMUyIsInZhbHVlcyI6WyI1MjAiLCIxNTkiLCIxMjMiLCIzMyIsIjkwMDA3NDEiXX0seyJpdGVtIjoiRElTQ0lQTElORSIsIm9wZXJhdG9yIjoiTk9UX0VRVUFMUyIsInZhbHVlcyI6WyJTdHJhdGVneSJdfSx7Iml0ZW0iOiJESVNDSVBMSU5FIiwib3BlcmF0b3IiOiJFUVVBTFMiLCJ2YWx1ZXMiOlsiRWNvbm9taWNzIl19LHsiaXRlbSI6IkFOQUxZU1QiLCJvcGVyYXRvciI6IkVRVUFMUyIsInZhbHVlcyI6WyJFMTQ0ODEyIiwiUjI5NzI1MCIsIk83MjA4MTUiLCJONzg2OTU1IiwiUjAyMDY3MCJdfSx7Im9wZXJhdG9yIjoiT1IiLCJjaGlsZHJlbiI6W3siaXRlbSI6IkNPVU5UUlkiLCJvcGVyYXRvciI6IkVRVUFMUyIsInZhbHVlcyI6WyJVUyJdfSx7Iml0ZW0iOiJSRUdJT04iLCJvcGVyYXRvciI6IkVRVUFMUyIsInZhbHVlcyI6WyJOb3J0aEFtZXJpY2EiXX1dfV19LHsib3BlcmF0b3IiOiJBTkQiLCJjaGlsZHJlbiI6W3siaXRlbSI6IlBVQkxJQ0FUSU9OX0lEIiwib3BlcmF0b3IiOiJOT1RfRVFVQUxTIiwidmFsdWVzIjpbIjkwMDA4MTEiXX0seyJpdGVtIjoiUFVCTElDQVRJT05fSUQiLCJvcGVyYXRvciI6Ik5PVF9FUVVBTFMiLCJ2YWx1ZXMiOlsiMTU5IiwiMTIzIl19LHsiaXRlbSI6IkFOQUxZU1QiLCJvcGVyYXRvciI6IkVRVUFMUyIsInZhbHVlcyI6WyJVMDA0NzIwIl19XX1dfX1dfSZ0YWI9QWxsUmVzdWx0cw%3D%3D",
    "Citi": "https://www.citivelocity.com/cv2/go/CV_OneSearch_Result/X19OQVZJR0FUSU9OX0JBU0U2NF9fL0NvbXBvc2l0ZVBhZ2VTZXJ2aWNlL3BhZ2UvY3ZzZWFyY2hyZXN1bHRwYWdlL0NWX1NJR05BTF9QQUdFX0NBQ0hFI2NudHJDb2RlPUNWX1NJR05BTF9QQUdFJkRVTT1mYWxzZSZzPU40SWdvZ3hnOWdkbEMyQkxDQlNBVEFCZ0lJd0lZQnNCUEFaMFdKQUM1UnlxUUFYU2tBTTNnRmQ4UUFhRUFDMXhvRGFvUHNSNTFjQWN3QXFoQUE0QlRTZ0pERldBSXdCVzhpSFR6eEZBWFc0d2w0YUhDU3BNT0FpVElnaklSQUJORzIyQW1TNDhSVXVXN0VBRTRRakFEQ0FHcWhzSFR5TUF6Y0RCVE1QQ0FBdm83RThyakJQQURTOG9RQTdsQ0JyclNKekFEV1hDQW1TWkFlbHVqWVBuYitJTEtzZ2ZMNVJTVmxJRFhFRldCeGlIU0VhYW5jUEZLTURSYkl6VGErOXFtcFFBJnV1aWQ9MTc4ODc2NzEyNjA2MCZzaWduYWxUeXBlPWhhc2h0YWdz",
    "BofA": "https://markets.ml.com/economics-overview",
}


def months_before(day: date, months: int) -> date:
    y, m = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(y, m + 1, min(day.day, calendar.monthrange(y, m + 1)[1]))


def parse_date(text: str, now: datetime | None = None) -> date | None:
    """Read publication dates, never infer from download time except relative labels."""
    now = now or datetime.now(KST)
    text = text.strip()
    rel = re.fullmatch(r"(?:about\s+)?(\d+)\s+(minute|hour|day|week)s?\s+ago", text, re.I)
    if rel:
        return (now - timedelta(**{rel[2].lower() + "s": int(rel[1])})).date()
    if text.lower() in ("today", "just now"):
        return now.date()
    if text.lower() == "yesterday":
        return (now - timedelta(days=1)).date()
    patterns = (
        (r"\b(\d{4})-(\d{2})-(\d{2})(?=T|\b)", "iso"),
        (r"\b(\d{1,2})[- ]([A-Za-z]{3,9})[- ](\d{4}|\d{2})\b", "dmy"),
        (r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b", "mdy"),
    )
    for pattern, kind in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        a, b, c = match.groups()
        try:
            if kind == "iso":
                return date(int(a), int(b), int(c))
            year = int(c) + (2000 if len(c) == 2 else 0)
            mon, day = (b, a) if kind == "dmy" else (a, b)
            return date(year, MONTHS[mon[:3].lower()], int(day))
        except (ValueError, KeyError):
            continue
    return None


def is_pdf(raw: bytes) -> bool:
    # Reject HTML login/error pages and incomplete transfers, regardless of suffix.
    return len(raw) >= 100 and raw[:1024].lstrip().startswith(b"%PDF-") and b"%%EOF" in raw[-8192:]


def safe_filename(title: str, doc_id: str, published: date) -> str:
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title)
    title = re.sub(r"\s+", " ", title).strip(" .")[:64] or "report"
    suffix = hashlib.sha256(doc_id.encode()).hexdigest()[:12]
    return f"{published:%Y%m%d}_{title}__{suffix}.pdf"


def atomic_write_json(path: Path, value) -> None:
    """Write a JSON artifact without leaving a half-written latest-run file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run_artifact_paths(log_root: Path, run_id: str) -> tuple[Path, Path, Path]:
    """Keep each invocation's text log and summary together by calendar day."""
    day_folder = log_root / f"{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]}"
    day_folder.mkdir(parents=True, exist_ok=True)
    return (
        day_folder / f"run_{run_id}.log",
        day_folder / f"run_{run_id}.json",
        log_root / "latest_run.json",
    )


def configure_logging(state_dir: Path, run_log: Path) -> None:
    """Log both to the legacy cumulative file and a self-contained run file."""
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(state_dir / "collector.log", encoding="utf-8"),
        logging.FileHandler(run_log, encoding="utf-8"),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


@dataclass
class Report:
    house: str
    doc_id: str
    title: str
    date_text: str
    url: str
    source_url: str
    element_id: str = ""
    region: str = ""
    published: str = ""

    def __post_init__(self):
        if self.house not in HOUSES:
            raise ValueError("Unknown house")
        if not self.published:
            day = parse_date(self.date_text)
            self.published = day.isoformat() if day else ""


class Incomplete(RuntimeError):
    """The collector could not establish full list coverage."""


class NoOriginalPDF(RuntimeError):
    """A loaded content page positively identifies a newsletter or media item."""


def driver_disconnected(context, exc=None) -> bool:
    """Do not issue cleanup commands on a transport known to have died."""
    if exc is not None and 'Connection closed while reading from the driver' in str(exc):
        return True
    browser = getattr(context, 'browser', None)
    return browser is not None and not browser.is_connected()


def dismiss_dialog_safely(dialog):
    """Keep a dialog that closed concurrently from crashing automatic dismissal."""
    try:
        dialog.dismiss()
    except Exception as exc:
        # Do not log dialog.message: it can contain account-specific text.
        LOG.warning('Dialog dismissal did not complete: %s', str(exc).splitlines()[0][:200])


def minimize_page_in_collector(context, page):
    """Use the collector's single driver; a second CDP client can race dialogs."""
    if page.is_closed() or driver_disconnected(context):
        return
    session = None
    try:
        session = context.new_cdp_session(page)
        window = session.send('Browser.getWindowForTarget')
        session.send('Browser.setWindowBounds', {
            'windowId': window['windowId'], 'bounds': {'windowState': 'minimized'}})
    except Exception:
        LOG.debug('Could not minimize this macro window', exc_info=True)
    finally:
        if session is not None and not driver_disconnected(context):
            try:
                session.detach()
            except Exception:
                pass


class State:
    def __init__(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        self.folder = folder
        self.db = sqlite3.connect(folder / "downloads.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS reports (
              house TEXT, doc_id TEXT, title TEXT, published TEXT, url TEXT,
              source_url TEXT, region TEXT, status TEXT DEFAULT 'pending',
              path TEXT DEFAULT '', sha256 TEXT DEFAULT '', bytes INTEGER DEFAULT 0,
              attempts INTEGER DEFAULT 0, error TEXT DEFAULT '', updated TEXT,
              PRIMARY KEY(house,doc_id));
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY, started TEXT, finished TEXT, mode TEXT,
              start_date TEXT, end_date TEXT, summary TEXT);
        """)

    def record(self, r: Report):
        self.db.execute("""INSERT INTO reports
          (house,doc_id,title,published,url,source_url,region,updated)
          VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(house,doc_id) DO UPDATE SET
          title=excluded.title,published=excluded.published,url=excluded.url,
          source_url=excluded.source_url,updated=excluded.updated""",
          (r.house,r.doc_id,r.title,r.published,r.url,r.source_url,r.region,datetime.now(KST).isoformat()))
        self.db.commit()

    def downloaded(self, r: Report) -> bool:
        row = self.db.execute("SELECT * FROM reports WHERE house=? AND doc_id=?", (r.house,r.doc_id)).fetchone()
        if not row or row["status"] != "downloaded":
            return False
        try:
            raw = Path(row["path"]).read_bytes()
            return is_pdf(raw) and hashlib.sha256(raw).hexdigest() == row["sha256"]
        except OSError:
            return False

    def known_no_original_pdf(self, r: Report) -> bool:
        row = self.db.execute(
            "SELECT status,path,sha256 FROM reports WHERE house=? AND doc_id=?", (r.house, r.doc_id)
        ).fetchone()
        if not row or row['status'] != 'no_original_pdf':
            return False
        if row['path']:
            try:
                return hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256']
            except OSError:
                return False
        return True

    def result(self, r: Report, status: str, error: str = "", path: Path | None = None, raw: bytes = b""):
        self.db.execute("""UPDATE reports SET status=?, error=?, path=?, sha256=?, bytes=?,
          attempts=attempts+1, updated=? WHERE house=? AND doc_id=?""",
          (status,error,str(path) if path else "",hashlib.sha256(raw).hexdigest() if raw else "",
           len(raw),datetime.now(KST).isoformat(),r.house,r.doc_id))
        self.db.commit()

    def export(self):
        rows = self.db.execute("SELECT * FROM reports ORDER BY house,published,doc_id").fetchall()
        if rows:
            with (self.folder / "manifest.csv").open("w",encoding="utf-8-sig",newline="") as f:
                writer = csv.writer(f)
                writer.writerow(rows[0].keys())
                writer.writerows(tuple(r) for r in rows)


@contextmanager
def run_lock(folder: Path):
    """OS lock is released on crashes; a leftover lock file is harmless."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "collector.lock").open("a+b") as f:
        if f.seek(0, 2) == 0:
            f.write(b"0"); f.flush()
        f.seek(0)
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another collector is already running with this state directory.") from exc
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if sys.platform == "win32":
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def wait_until(fn: Callable, timeout: float = 35, interval: float = .4):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result:
                return result
        except Exception as exc:
            last = exc
        time.sleep(interval)
    raise Incomplete(f"Page did not reach the expected state ({type(last).__name__ if last else 'timeout'}). Check login or site layout.")


def frame_with(page, selector: str, timeout: float = 40):
    def find():
        for frame in page.frames:
            try:
                if frame.locator(selector).count():
                    return frame
            except Exception:
                pass
        return None
    return wait_until(find, timeout)


def visible(loc):
    for i in range(loc.count()):
        candidate = loc.nth(i)
        if candidate.is_visible() and candidate.is_enabled():
            return candidate
    return None


class PDFSaver:
    def __init__(self, context, output: Path, timeout: int = 120):
        self.context, self.output, self.timeout = context, output, timeout

    def request_pdf(self, url: str, referer: str) -> bytes | None:
        if not url.startswith(("http://", "https://")):
            return None
        response = None
        try:
            response = self.context.request.get(url, headers={"Referer":referer}, timeout=45000)
            if response.status in (401,403,429):
                LOG.debug("PDF request status %s; will try browser flow", response.status)
                return None
            if response.ok:
                raw = response.body()
                if is_pdf(raw):
                    return raw
        except Exception:
            LOG.debug("Direct request unavailable; trying browser flow")
        finally:
            if response:
                response.dispose()
        return None

    def save(self, r: Report, raw: bytes) -> Path:
        if not is_pdf(raw):
            raise ValueError("Not a complete original PDF")
        destination = self.output / r.house
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / safe_filename(r.title,r.doc_id,date.fromisoformat(r.published))
        part = path.with_suffix(".pdf.part")
        part.write_bytes(raw)
        part.replace(path)
        return path

    def gs_blog_evidence(self, r: Report, page, response) -> str:
        """Verify a rendered GS blog, excluding only the two observed legal PDFs."""
        from urllib.parse import urlsplit
        source, current = urlsplit(r.url), urlsplit(page.url)
        if (response is None or response.status != 200
                or 'text/html' not in response.headers.get('content-type', '').lower()
                or source.hostname != 'marquee.gs.com' or current.hostname != source.hostname
                or current.path != source.path
                or not re.fullmatch(r'/content/research/en/blogs/\d{4}/\d{2}/\d{2}/[^/]+\.html', current.path)
                or current.path.rsplit('/', 1)[-1] != r.doc_id + '.html'):
            return ''
        script = r"""() => {
          const body=document.body?.innerText || '';
          const label=e=>[e.innerText,e.title,e.getAttribute('aria-label')].filter(Boolean).join(' ');
          const links=[...document.querySelectorAll('a,button,[role="button"]')]
            .filter(e=>/\bPDF\b|\.pdf(?:[?#]|$)/i.test(label(e)+' '+(e.getAttribute('href')||'')))
            .map(e=>({label:label(e),href:e.getAttribute('href')||''}));
          return {body,ready:document.readyState,links,
            embedded:!!document.querySelector('object[type="application/pdf"],embed[type="application/pdf"]'),
            blocked:[...document.querySelectorAll('input[type="password"]')].some(e=>e.getClientRects().length) ||
              /please (?:log|sign) in|access denied|not entitled|session (?:has )?expired/i.test(body)};
        }"""
        try:
            snapshots = [frame.evaluate(script) for frame in page.frames]
        except Exception:
            return ''
        legal_pdfs = {
            'https://www.goldmansachs.com/disclosures/interest-rate-benchmark-transition-notice.pdf',
            'https://marquee.gs.com/content/dam/research/securityguidance2021.pdf',
        }
        if not snapshots or any(s['blocked'] or s['embedded'] for s in snapshots):
            return ''
        if any(urljoin(page.url, link['href']) not in legal_pdfs
               for s in snapshots for link in s['links']):
            return ''
        main = snapshots[0]
        body = re.sub(r'\s+', ' ', main['body'])
        if (main['ready'] not in ('interactive', 'complete') or len(body) < 500
                or re.sub(r'\s+', ' ', r.title) not in body
                or not re.search(r'Research\s*\|.*?\|\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}', body)
                or 'Goldman Sachs All rights reserved.' not in body):
            return ''
        return ('Verified complete GS research blog with matching URL/title, publication stamp and footer; '
                'only generic legal PDF links are present, with no original article PDF control.')

    def archive_gs_blog(self, r: Report, page, evidence: str):
        folder = self.output / 'GS' / 'html'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / Path(safe_filename(r.title, r.doc_id, date.fromisoformat(r.published))).with_suffix('.html')
        raw = page.content().encode('utf-8')
        temporary = path.with_suffix('.html.part')
        temporary.write_bytes(raw)
        temporary.replace(path)
        path.with_suffix('.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
        atomic_write_json(path.with_suffix('.json'), {
            'house': r.house, 'doc_id': r.doc_id, 'title': r.title, 'published': r.published,
            'source_url': r.url, 'saved': datetime.now(KST).isoformat(),
            'format': 'html', 'path': str(path), 'note': evidence,
        })
        return path, raw

    def no_original_pdf_evidence(self, r: Report, page, response) -> str:
        """Recognize only verified HSBC HTML templates, never missing controls alone."""
        from urllib.parse import urlsplit
        if r.house == 'GS':
            return self.gs_blog_evidence(r, page, response)
        if r.house != 'HSBC' or response is None or response.status != 200:
            return ''
        if 'text/html' not in response.headers.get('content-type','').lower():
            return ''
        source,current=urlsplit(r.url),urlsplit(page.url)
        if source.hostname != 'www.research.hsbc.com' or current.hostname != source.hostname:
            return ''
        if current.path != source.path or current.path.rstrip('/').split('/')[-1] != r.doc_id:
            return ''
        if not re.fullmatch(r'/(?:O|R/10)/[^/]+',current.path):
            return ''
        try:
            snapshots=[frame.evaluate(HSBC_CONTENT_EVIDENCE) for frame in page.frames]
        except Exception:
            return ''
        if not snapshots or any(s['blocked'] or s['pdf_control'] for s in snapshots):
            return ''
        main=snapshots[0]
        if main['ready'] not in ('interactive','complete'):
            return ''
        if current.path.startswith('/O/'):
            title=main['newsletter_title']
            if (re.fullmatch(r'(?:Macro Matters - (?:EMEA|Americas|Asia-Pacific)|Global Essentials)',title)
                    and main['newsletter_date'] and parse_date(main['newsletter_date']) == date.fromisoformat(r.published)
                    and main['focus_reports'] >= 2 and main['newsletter_actions'] and main['linked_report_disclosures']):
                return (f'Verified HSBC HTML newsletter: {title}; publication {r.published}; '
                        f'{main["focus_reports"]} linked Research Focus entries, Subscribe/plain Print controls; '
                        'no original PDF/download control in any frame.')
        elif main['media_player'] and main['media_disclosures']:
            return ('Verified HSBC standalone media page: video-container with video-js player and Play Video control; '
                    'content disclosures present; no original PDF/download control in any frame. '
                    'Related full reports are separate catalog items.')
        return ''

    def download(self, r: Report, source_page, click=None) -> bytes:
        # JPM's direct route is also used by the user's existing QAE downloader.
        direct = r.url if r.house == "HSBC" else ""
        if r.house == "JPM":
            direct = f"https://markets.jpmorgan.com/research/ArticleServlet?doc={r.doc_id}.pdf"
        if direct and click is None:
            raw = self.request_pdf(direct,r.source_url)
            if raw:
                return raw

        work = self.context.new_page()
        owned = [work]
        watched = set()
        downloads, pdf_responses = [], []
        clicked, requested = set(), set()

        def on_download(download):
            downloads.append(download)

        def on_response(response):
            try:
                if "application/pdf" in response.headers.get("content-type", "").lower():
                    pdf_responses.append(response)
            except Exception:
                pass

        def watch(page):
            if page in watched:
                return
            watched.add(page)
            page.on("download", on_download)
            page.on("response", on_response)

        def on_page(page):
            try:
                if page.opener() in watched:
                    owned.append(page); watch(page)
            except Exception:
                pass

        watch(work)
        if click:
            watch(source_page)
        self.context.on("page", on_page)
        try:
            document_response=None
            try:
                if click:
                    click()
                else:
                    document_response=work.goto(r.url, wait_until="commit",timeout=45000)
            except Exception:
                # A real attachment aborts normal navigation; process the download event.
                pass
            deadline = time.monotonic() + self.timeout
            non_pdf_evidence=''; non_pdf_since=None
            while time.monotonic() < deadline:
                while downloads:
                    dl = downloads.pop(0)
                    temp = self.output / r.house / f".incoming-{uuid.uuid4().hex}.part"
                    temp.parent.mkdir(parents=True,exist_ok=True)
                    try:
                        dl.save_as(str(temp))
                        raw = temp.read_bytes()
                        if is_pdf(raw):
                            return raw
                    finally:
                        temp.unlink(missing_ok=True)
                while pdf_responses:
                    try:
                        raw = pdf_responses.pop(0).body()
                        if is_pdf(raw):
                            return raw
                    except Exception:
                        pass
                for page in list(owned):
                    if page.is_closed():
                        continue
                    for frame in page.frames:
                        try:
                            # Only explicitly labelled original-document controls, not arbitrary .pdf links.
                            controls = frame.locator('a#print_pdf_anchor, a[title="PDF"], a[aria-label="PDF"]')
                            control = visible(controls) or visible(frame.get_by_role("link",name="PDF",exact=True))
                            if not control:
                                control = visible(frame.get_by_role("button",name=re.compile(r"^(?:Print|印刷)\s*\(PDF")))
                            if not control:
                                control = visible(frame.get_by_role("button",name=re.compile(r"^(Download|Download PDF|PDF)$",re.I)))
                            if control:
                                href = control.get_attribute("href") or ""
                                if href.startswith(("http", "/")):
                                    full = urljoin(frame.url,href)
                                    if full not in requested:
                                        requested.add(full)
                                        raw = self.request_pdf(full,frame.url)
                                        if raw:
                                            return raw
                                key = (page,frame.url,control.get_attribute("id"),control.get_attribute("aria-label"),href,control.inner_text())
                                if key not in clicked:
                                    clicked.add(key); control.click(timeout=6000)
                            elif r.house == "Citi":
                                pane = visible(frame.locator('#printTabButton'))
                                key = (page,frame.url,"citi_print_pane")
                                if pane and key not in clicked:
                                    clicked.add(key); pane.click(timeout=6000)
                        except Exception:
                            continue
                    page.wait_for_timeout(250)
                if not work.is_closed() and not downloads and not pdf_responses:
                    evidence=self.no_original_pdf_evidence(r,work,document_response)
                    if evidence and evidence == non_pdf_evidence:
                        if time.monotonic()-non_pdf_since >= 2:
                            unavailable = NoOriginalPDF(evidence)
                            if r.house == 'GS':
                                unavailable.archive_path, unavailable.archive_raw = self.archive_gs_blog(r, work, evidence)
                            raise unavailable
                    else:
                        non_pdf_evidence=evidence
                        non_pdf_since=time.monotonic() if evidence else None
                if not any(not p.is_closed() for p in owned):
                    source_page.wait_for_timeout(250)
            raise Incomplete("Original PDF did not arrive; check login, entitlement, or PDF button. HTML was not saved as PDF.")
        finally:
            disconnected = driver_disconnected(self.context, sys.exc_info()[1])
            self.context.remove_listener("page",on_page)
            for page in watched:
                try:
                    page.remove_listener("download",on_download)
                    page.remove_listener("response",on_response)
                except Exception:
                    pass
            for page in owned:
                if not disconnected and not page.is_closed():
                    try:
                        page.close()
                    except Exception as exc:
                        disconnected = driver_disconnected(self.context, exc)
                        LOG.warning('[%s] could not close owned report page: %s', r.house, exc)


# Observed on HSBC's /O newsletters and /R/10 standalone video/podcast pages.
# Inspect rendered content only; PDF controls (including hidden ones) block classification.
HSBC_CONTENT_EVIDENCE = r"""() => {
  const visible = el => !!el && !!el.getClientRects().length;
  const text = el => el ? (el.innerText || '').trim() : '';
  const body = text(document.body);
  const controls = [...document.querySelectorAll('a,button,[role="button"],input[type="button"]')];
  const label = el => [el.innerText,el.getAttribute('title'),el.getAttribute('aria-label'),el.value].filter(Boolean).join(' ').trim();
  const pdfControl = controls.some(el => /\bPDF\b|^Download\b/i.test(label(el)) || /\.pdf(?:[?#]|$)/i.test(el.getAttribute('href') || '')) ||
    !!document.querySelector('a#print_pdf_anchor,object[type="application/pdf"],embed[type="application/pdf"]');
  const title = document.querySelector('#firstTitleBoxTitle');
  const stamp = document.querySelector('#firstTitleBoxDate');
  const actions = [...document.querySelectorAll('#printSubscribe a')].filter(visible);
  const player = document.querySelector('#main-container #video-container video-js');
  const play = document.querySelector('#video-container .vjs-big-play-button');
  return {
    ready:document.readyState,
    blocked:[...document.querySelectorAll('input[type="password"]')].some(visible) ||
      /please (?:log|sign) in|sign in to (?:continue|access)|access denied|not authori[sz]ed|not entitled|session (?:has )?expired|temporarily unavailable/i.test(body),
    pdf_control:pdfControl,
    newsletter_title:visible(title)?text(title):'', newsletter_date:visible(stamp)?text(stamp):'',
    focus_reports:[...document.querySelectorAll('#researchFocusPortletContent .focusReport')].filter(visible).filter(el=>el.querySelector('a[href*="/R/"]')).length,
    newsletter_actions:actions.some(el=>text(el)==='Subscribe' && el.getAttribute('onclick')==='subscriptions()') &&
      actions.some(el=>text(el)==='Print' && el.getAttribute('onclick')==='printRMPDocument()'),
    linked_report_disclosures:/Please refer to the report links below for these Important Disclosures and Disclaimers\./i.test(body),
    media_player:visible(player) && !!player.querySelector('video.vjs-tech') && visible(play) && /Play Video/i.test(label(play)),
    media_disclosures:/Disclosures, analyst certifications, and disclaimers that must be viewed with this content/i.test(body) &&
      /Copyright HSBC Bank plc/i.test(body)
  };
}"""


# DOM extraction stays confined to report lists. No application tokens or private APIs are read.
EXTRACT = r"""({house, base, region}) => {
  const text = el => el ? (el.innerText || el.textContent || '').trim() : '';
  let rows = [];
  if (house === 'HSBC') {
    rows = [...document.querySelectorAll('#allReportsTable tr.reportTableRow')].map(tr => {
      const a=tr.querySelector('td.titleTableCell a[href]');
      return a && {id:a.pathname.split('/').pop(), title:text(tr.querySelector('td.titleTableCell')),
        date:text(tr.querySelector('td.pubdateTableCell')), url:a.href};
    });
  } else if (house === 'GS') {
    rows = [...document.querySelectorAll('tr')].filter(tr=>tr.getClientRects().length).map(tr => {
      const a=tr.querySelector('a[href*="/content/research/en/reports/"], a[href*="/content/research/en/blogs/"]');
      if(!a) return null;
      const cells=[...tr.querySelectorAll('td')];
      return {id:a.pathname.split('/').pop().replace(/\.html$/,''),title:text(a),
        date:cells.map(text).find(t=>/\d{1,2}\s+[A-Za-z]{3}\s+\d{4}/.test(t))||'',url:a.href};
    });
  } else if (house === 'JPM') {
    rows = [...document.querySelectorAll('li')].filter(li=>li.getClientRects().length).map(li => {
      const a=li.querySelector('a[href*="/research/content/GPS-"]');
      if(!a) return null;
      const dates=text(li).match(/\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b/g)||[];
      return {id:a.pathname.split('/').pop(),title:text(a),date:dates.at(-1)||'',url:a.href};
    });
  } else if (house === 'Citi') {
    rows = [...document.querySelectorAll('.article-item-body')].filter(el=>el.getClientRects().length).map(el=>{
      const a=el.querySelector('a[href*="/smartlink/research/"]');
      return a && {id:a.pathname.split('/').pop(),title:text(a),date:text(el.querySelector('time')),url:a.href};
    });
  } else if(house === 'BofA') {
    rows = [...document.querySelectorAll('tr')].filter(tr=>tr.getClientRects().length && !tr.querySelector('table')).map(tr=>{
      const a=tr.querySelector('a[onclick*="htmlIconClickOnCachedPortlet"]');
      if(!a) return null;
      const id=(a.getAttribute('onclick').match(/\('(\d+)'/)||[])[1];
      const dates=text(tr).match(/\b\d{1,2}-[A-Za-z]{3}-\d{4}\b/g)||[];
      const title=a.querySelector('.bold-text');
      const cell=a.closest('td');
      const subtitle=cell ? [...cell.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).filter(Boolean).join(' ') : '';
      return id && {id,title:(text(title)||text(a))+(subtitle?' — '+subtitle:''),date:dates.at(-1)||'',url:'',element_id:a.id};
    });
  }
  const seen=new Set();
  return rows.filter(Boolean).filter(r=>r.id && !seen.has(r.id) && seen.add(r.id));
}"""


def extract(frame, house: str, page_url: str, region="") -> list[Report]:
    rows = frame.evaluate(EXTRACT, {"house":house,"base":page_url,"region":region})
    return [Report(house,x["id"],x["title"],x["date"],x["url"],page_url,x.get("element_id",""),region) for x in rows]


def signature(rows):
    return tuple(r.doc_id for r in rows)


def all_before(rows, start: date) -> bool:
    # A single pinned old item must never terminate a scan.
    return bool(rows) and all(r.published and date.fromisoformat(r.published) < start for r in rows)


def select_hsbc_date(page, selector: str, day: date):
    # Inputs are readonly: use the real datepicker so hidden values update too.
    page.locator(selector).click()
    calendar_popup = page.locator('#ui-datepicker-div')
    calendar_popup.locator('.ui-datepicker-year').select_option(str(day.year))
    calendar_popup.locator('.ui-datepicker-month').select_option(str(day.month-1))
    calendar_popup.get_by_role('link',name=str(day.day),exact=True).click()
    if parse_date(page.locator(selector).input_value()) != day:
        raise Incomplete('HSBC datepicker did not select the requested date.')


def hsbc_results_ready(page, start=None, end=None):
    # The filter controls render before the first AJAX result.  Key Reports has
    # its own independently loaded "No Reports Found" cell; it is not evidence
    # that All Reports is empty.  Read only the result's date provenance, never
    # export the full sort URL (which can also contain a session identifier).
    info=page.evaluate("""() => {
      const table=document.querySelector('#allReportsTable');
      const query=new URLSearchParams(document.querySelector('#allReportsSortDateURL')?.value||'');
      const empty=table?.querySelector('#noReportsCell');
      return {visible:!!table?.getClientRects().length,
        empty:!!empty?.getClientRects().length && /No Reports Found/i.test(empty.innerText),
        dates:['datespecific','datefromday','datefrommonth','datetoday','datetomonth'].map(k=>query.get(k))};
    }""")
    if not info['visible']:
        return None
    if start is not None:
        expected=['between',start.strftime('%d'),start.strftime('%Y%m'),
                  end.strftime('%d'),end.strftime('%Y%m')]
        if info['dates'] != expected:
            return None
    rows=extract(page.main_frame,'HSBC',page.url)
    if rows:
        if start is None or all(r.published and start<=date.fromisoformat(r.published)<=end for r in rows):
            return rows
        return None
    return 'empty' if info['empty'] else None


def pagination_end_evidence(frame, house: str, total: int, page_no: int, advertised_total=None) -> str:
    """Require affirmative last-page evidence when an enabled Next is absent.

    Missing controls can mean an unfinished render, changed layout, or expired
    session.  They are never, by themselves, proof that the catalog ended.
    ``total`` is the number of distinct report IDs visited in this traversal.
    """
    position = None
    if house in ('GS', 'JPM'):
        positions = set(re.findall(r'\bPage\s+(\d+)\s+of\s+(\d+)\b',
                                   frame.locator('body').inner_text(), re.I))
        if len(positions) > 1:
            raise Incomplete(f'{house} exposes conflicting page counts; catalog end is unverified.')
        if positions:
            current, last = map(int, positions.pop())
            if current < 1 or last < current or current != page_no:
                raise Incomplete(f'{house} page position is inconsistent with the pages visited.')
            if current < last:
                raise Incomplete(f'{house} still advertises later pages, but Next is unavailable.')
            position = f'Page {current} of {last}'
    elif house == 'HSBC':
        # This result list is capped at 75 rows (five 15-row pages). Its
        # full pager consists of current_page/dummyHyperlink numeric spans.
        # Reject gaps and an unexpected starting page instead of interpreting
        # a moving/truncated page-number window as the catalog's last page.
        paging = frame.locator('#allReportsPageNumbers')
        if paging.count() == 1 and paging.is_visible():
            current = paging.locator('.current_page')
            if current.count() == 1:
                current_text = current.inner_text().strip()
                numbers = sorted(set(int(n) for n in re.findall(r'\b\d+\b', paging.inner_text())))
                if current_text.isdigit() and numbers:
                    current_no, last = int(current_text), numbers[-1]
                    if (last > 5 or numbers != list(range(1, last + 1))
                            or current_no != page_no or current_no not in numbers):
                        raise Incomplete('HSBC page position does not establish a complete traversal.')
                    if current_no < last:
                        raise Incomplete('HSBC still advertises later pages, but Next is unavailable.')
                    position = f'HSBC complete pager {current_no}/{last}'
    if advertised_total is not None:
        if type(advertised_total) is not int or advertised_total < 1 or total != advertised_total:
            raise Incomplete(f'Next page is unavailable after {total} distinct rows, but the site advertises {advertised_total} documents.')
        return f'advertised total {advertised_total} distinct documents'
    if position:
        return position
    raise Incomplete(f'{house} Next is unavailable before the date boundary, and no verified last-page evidence is present.')


class Collector:
    def __init__(self, context, args, state, start, end, urls):
        self.context,self.args,self.state,self.start,self.end,self.urls=context,args,state,start,end,urls
        self.saver = PDFSaver(context,args.output,args.pdf_timeout)
        self.counts = {h:Counter() for h in HOUSES}
        self.seen = set()

    def consume(self, rows, page):
        for r in rows:
            key=(r.house,r.doc_id)
            if key in self.seen:
                continue
            self.seen.add(key)
            count=self.counts[r.house]
            count["discovered"]+=1
            if not r.published:
                self.state.record(r)
                self.state.result(r,"unknown_date","Publication date was not parseable; not downloaded.")
                count["unknown_date"]+=1
                continue
            if not self.start <= date.fromisoformat(r.published) <= self.end:
                count["outside_range"]+=1
                continue
            self.state.record(r)
            count["in_range"]+=1
            if self.state.downloaded(r):
                count["already_saved"]+=1
                continue
            if self.state.known_no_original_pdf(r):
                count["no_original_pdf"]+=1
                continue
            if self.args.mode == "scan":
                count["listed"]+=1
                continue
            if self.args.limit and count["attempted"] >= self.args.limit:
                raise Incomplete("Stopped at the explicitly requested --limit; run again without it for full coverage.")
            count["attempted"]+=1
            for attempt in range(self.args.retries):
                try:
                    click = None
                    if r.house == "BofA":
                        # Exact current-list element; no guessed report URL or dynamic function execution.
                        click = lambda ident=r.element_id: page.locator('[id='+json.dumps(ident)+']').click(timeout=10000)
                    elif r.house == "JPM":
                        # Missing controls belong to this report's retry/failure state.
                        selector='button[data-testid="download-button"][id='+json.dumps(r.doc_id)+']'
                        frame=frame_with(page,selector,timeout=12)
                        click=lambda frame=frame,selector=selector: frame.locator(selector).click(timeout=10000)
                    raw=self.saver.download(r,page,click)
                    path=self.saver.save(r,raw)
                    self.state.result(r,"downloaded",path=path,raw=raw)
                    count["downloaded"]+=1
                    LOG.info("[%s] saved %s (%s KB)",r.house,path.name,len(raw)//1024)
                    break
                except NoOriginalPDF as exc:
                    archive_path = getattr(exc, 'archive_path', None)
                    self.state.result(r,'no_original_pdf',str(exc),path=archive_path,
                                      raw=getattr(exc, 'archive_raw', b''))
                    count['no_original_pdf']+=1
                    if archive_path:
                        count['archived_html']+=1
                        LOG.info('[%s] archived HTML %s',r.house,archive_path.name)
                    LOG.info('[%s] no original PDF %s: %s',r.house,r.doc_id,exc)
                    break
                except Exception as exc:
                    error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:240]}"
                    self.state.result(r,"failed",error)
                    if attempt+1 == self.args.retries:
                        count["failed"]+=1
                        LOG.warning("[%s] failed %s: %s",r.house,r.doc_id,error)
                    else:
                        time.sleep(min(15,2**(attempt+1)))
            time.sleep(self.args.delay)

    def paginated(self, page, house, frame, next_locator, region="", start=None, advertised_total=None):
        floor=start or self.start
        seen_pages=set(); seen_reports=set(); total=0
        for page_no in range(1,self.args.max_pages+1):
            rows=extract(frame,house,page.url,region)
            if not rows:
                raise Incomplete("Empty or unreadable report list. Login or search results need verification.")
            sig=signature(rows)
            if sig in seen_pages:
                raise Incomplete("Pagination repeated a page; refusing to claim complete history.")
            seen_pages.add(sig); seen_reports.update(sig); total=len(seen_reports)
            LOG.info("[%s%s] page %s, %s rows, oldest=%s",house,':'+region if region else '',page_no,len(rows),min((r.published or 'unknown') for r in rows))
            self.consume(rows,page)
            if all_before(rows,floor):
                return total,"cutoff"
            button=visible(next_locator())
            if not button:
                evidence=pagination_end_evidence(frame,house,total,page_no,advertised_total)
                LOG.info('[%s%s] verified catalog end: %s',house,':'+region if region else '',evidence)
                return total,"end"
            button.click(timeout=10000)
            wait_until(lambda: signature(extract(frame,house,page.url,region)) not in ((),sig),45)
            time.sleep(self.args.delay)
        raise Incomplete("--max-pages reached before the requested date boundary.")

    def gs(self,page):
        page.goto(self.urls['GS'],wait_until="domcontentloaded")
        frame=frame_with(page,'a[href*="/content/research/en/reports/"]')
        self.paginated(page,'GS',frame,lambda:frame.get_by_role('link',name=re.compile(r'^Next')))

    def jpm(self,page):
        page.goto(self.urls['JPM'],wait_until="domcontentloaded",timeout=60000)
        frame=frame_with(page,'a[href*="/research/content/GPS-"]')
        # JPM remembers the last search page across visits, including backfills.
        # Always return to the newest page before applying the date cutoff.
        previous=frame.get_by_role('button',name='Previous Page',exact=True)
        if previous.count() and not previous.is_disabled():
            old_signature=signature(extract(frame,'JPM',page.url))
            frame.get_by_role('button',name=re.compile(r'^Page 1 of ')).click()
            wait_until(lambda: previous.is_disabled() and
                       signature(extract(frame,'JPM',page.url)) not in ((),old_signature),45)
        self.paginated(page,'JPM',frame,lambda:frame.get_by_role('button',name='Next Page',exact=True))

    def hsbc(self,page):
        # The legacy list has a server-side result cap. Weekly slices are split again if necessary.
        slices=[]; current=self.start
        while current<=self.end:
            stop=min(self.end,current+timedelta(days=6)); slices.append((current,stop)); current=stop+timedelta(days=1)
        while slices:
            start,end=slices.pop()
            LOG.info('[HSBC] date slice %s..%s',start,end)
            page.goto(self.urls['HSBC'],wait_until="domcontentloaded")
            frame_with(page,'#mainFilters')
            # Finish the initial list load before submitting a new search.  A
            # late initial response must not overwrite the date-filtered list.
            wait_until(lambda:hsbc_results_ready(page),45)
            if not page.locator('#mainFilters').is_visible():
                page.get_by_text('Advanced Search',exact=True).click()
            page.locator('#mainFilters').select_option('8')
            dialog=page.get_by_role('dialog')
            dialog.get_by_role('radio',name='Between',exact=True).check()
            for field,day in [('#dateFromDisp',start),('#dateToDisp',end)]:
                select_hsbc_date(page,field,day)
            dialog.get_by_role('link',name='Select',exact=True).click()
            page.get_by_role('link',name='Search',exact=True).click()
            loaded=wait_until(lambda:hsbc_results_ready(page,start,end),45)
            if loaded=='empty':
                LOG.info('[HSBC] verified empty date slice %s..%s',start,end)
                continue
            total,reason=self.paginated(page,'HSBC',page.main_frame,lambda:page.locator('#allReports .npLink').filter(has_text=re.compile(r'^\s*Next\s*$')),start=start)
            LOG.info('[HSBC] date slice %s..%s finished: %s rows (%s)',start,end,total,reason)
            if total>=75 and reason=='end':
                if start==end:
                    raise Incomplete(f"HSBC returned at least 75 rows for {start}; possible result cap. Narrow further on the site.")
                middle=start+(end-start)//2
                slices.extend([(start,middle),(middle+timedelta(days=1),end)])

    def bofa(self,page):
        regions={'Global':'Global','US/Can':'North America','Eur':'Europe','Jpn':'Japan','Aus/NZ':'Aus/NZ'}
        for region,search_region in regions.items():
            page.goto(self.urls['BofA'],wait_until="domcontentloaded",timeout=60000)
            frame_with(page,'a[onclick*="htmlIconClickOnCachedPortlet"]')
            page.get_by_role('tab',name=region,exact=True).first.click()
            # Other regional panels and other report sections remain in the DOM.
            # Use the visible More in the Most Recent Reports portlet only.
            more_links=page.locator('a[aria-label="read more reports"][href*="oAbegX4JUtoF"]')
            # Wait for the region-specific More link, not an arbitrary sleep after a tab click.
            def region_ready():
                link=visible(more_links)
                return link if link and search_region.casefold() in unquote(unquote(link.get_attribute('href') or '')).casefold() else None
            more=wait_until(region_ready,40)
            more.click()
            frame_with(page,'a[onclick*="htmlIconClickOnCachedPortlet"]')
            doc_match=wait_until(lambda: re.search(r'([\d,]+)\s+Documents',page.locator('body').inner_text()),35)
            total_docs=int(doc_match[1].replace(',',''))
            combo=page.locator('select').filter(has=page.locator('option',has_text='100 per page'))
            if combo.count():
                combo.first.select_option(label='100 per page')
                wait_until(lambda: len(extract(page.main_frame,'BofA',page.url,region))==min(100,total_docs),40)
            self.paginated(page,'BofA',page.main_frame,lambda:page.get_by_role('link',name='go to Next page',exact=True),region,advertised_total=total_docs)

    def citi(self,page):
        page.goto(self.urls['Citi'],wait_until="domcontentloaded")
        frame=frame_with(page,'.article-item-body a[href*="/smartlink/research/"]')
        research=frame.get_by_role('menuitem',name='Research',exact=True)
        if research.count():
            research.click()
            wait_until(lambda:extract(frame,'Citi',page.url),40)
        loaded_ids=set(); stalls=0
        for batch in range(self.args.max_pages):
            rows=extract(frame,'Citi',page.url)
            if not rows:
                raise Incomplete('Citi feed is empty or the login session expired.')
            new_ids=set(signature(rows))-loaded_ids
            if new_ids:
                loaded_ids.update(new_ids); stalls=0
                self.consume(rows,page)
                LOG.info('[Citi] %s distinct reports seen; oldest=%s',len(loaded_ids),min(r.published or 'unknown' for r in rows))
            else:
                stalls+=1
            dated=[date.fromisoformat(r.published) for r in rows if r.published]
            # Latest-first feed can accumulate rows rather than replacing each page.
            if len(dated)>=5 and len(dated)==len(rows) and all(d<self.start for d in dated[-5:]):
                return
            if stalls>=6:
                raise Incomplete('Citi feed stopped growing before the start date. Partial list only; archive/date search must be checked. Saved files can be resumed.')
            # Scroll the real feed container, including React custom scrollbars.
            frame.evaluate(r"""() => {
              const a=[...document.querySelectorAll('.article-item-body a[href*="/smartlink/research/"]')].at(-1);
              if(!a) return;
              a.scrollIntoView({block:'end'});
              for(let p=a.parentElement;p;p=p.parentElement) {
                if(p.scrollHeight>p.clientHeight+20 && /auto|scroll/.test(getComputedStyle(p).overflowY)) {
                  p.scrollTop=p.scrollHeight; p.dispatchEvent(new Event('scroll',{bubbles:true})); return;
                }
              }
              window.scrollTo(0,document.documentElement.scrollHeight);
            }""")
            page.wait_for_timeout(max(1800,int(self.args.delay*1000)))
        raise Incomplete('Citi maximum scroll batches reached before start date.')

    def run_house(self,house):
        page=None
        disconnected=False
        try:
            page=self.context.new_page(); page.set_default_timeout(12000)
            getattr(self,house.lower())(page)
            counts=self.counts[house]
            if counts['failed'] or counts['unknown_date']:
                return {'status':'incomplete','reason':'Failed PDFs or unparseable publication dates remain.','counts':dict(counts)}
            return {'status':'scan_complete' if self.args.mode=='scan' else 'complete',
                    'counts':dict(counts),'coverage_guard_version':1}
        except Exception as exc:
            disconnected=driver_disconnected(self.context,exc)
            LOG.error('[%s] incomplete: %s',house,exc)
            return {'status':'incomplete','reason':str(exc)[:600],'counts':dict(self.counts[house]),
                    'connection_lost':disconnected}
        finally:
            if page is not None and not disconnected and not driver_disconnected(self.context):
                try:
                    if not page.is_closed(): page.close()
                except Exception as exc:
                    LOG.warning('[%s] could not close collection page: %s',house,exc)
            self.state.export()


def run_requested_houses(collector, houses, checkpoint):
    """Keep requested but unfinished houses visible, even if execution is interrupted."""
    summary={house:{'status':'not_started','counts':{}} for house in houses}
    current=None
    try:
        checkpoint(summary,False)
        for current in houses:
            summary[current]={'status':'running','counts':dict(collector.counts[current])}
            checkpoint(summary,False)
            summary[current]=collector.run_house(current)
            checkpoint(summary,False)
            if summary[current].get('connection_lost'):
                LOG.error('Driver connection is gone; finalizing this run so the supervisor can retry in a fresh process.')
                break
    except KeyboardInterrupt:
        summary['interrupted']={'status':'incomplete','reason':'Stopped by user; rerun the same command to resume.'}
    except BaseException as exc:
        if current is not None:
            summary[current]={'status':'incomplete','reason':f'{type(exc).__name__}: {str(exc)[:600]}',
                              'counts':dict(collector.counts[current])}
        raise
    finally:
        for house in houses:
            if summary[house]['status'] in ('not_started','running'):
                summary[house]={'status':'incomplete',
                                'reason':'Run stopped before this house completed.' if house==current else 'Not started because the run stopped.',
                                'counts':dict(collector.counts[house])}
        checkpoint(summary,True)
    return summary


def parser():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter,allow_abbrev=False)
    p.add_argument('--mode',choices=['scan','backfill','daily','login','status'],default='scan')
    p.add_argument('--houses',nargs='+',choices=HOUSES,default=list(HOUSES))
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--state-dir',type=Path,default=Path(__file__).resolve().parent/'.collector')
    p.add_argument('--log-dir',type=Path,help='Per-run logs; default STATE_DIR/logs/YYYY-MM-DD')
    p.add_argument('--run-id',help='Optional unique run identifier for a staged collection campaign')
    p.add_argument('--profile-dir',type=Path,help='Dedicated automation Chrome profile; default .collector/chrome-profile')
    p.add_argument('--cdp-url',help='Optional existing automation Chrome endpoint, e.g. http://127.0.0.1:9222')
    p.add_argument('--months',type=int,default=9)
    p.add_argument('--start',type=date.fromisoformat,help='YYYY-MM-DD inclusive')
    p.add_argument('--end',type=date.fromisoformat,help='YYYY-MM-DD inclusive; default today in Korea')
    p.add_argument('--lookback-days',type=int,default=7,help='Daily mode overlap window')
    p.add_argument('--limit',type=int,default=0,help='Per-house download attempt limit; 0 = unlimited')
    p.add_argument('--max-pages',type=int,default=20000)
    p.add_argument('--delay',type=float,default=1.5)
    p.add_argument('--retries',type=int,default=3)
    p.add_argument('--pdf-timeout',type=int,default=120)
    p.add_argument('--headless',action='store_true')
    p.add_argument('--minimize-window',action='store_true',help='Minimize macro windows using this collector driver only')
    p.add_argument('--urls-json',type=Path,help='Optional house-to-start-URL overrides after a site changes')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.months<1 or args.lookback_days<1 or args.max_pages<1 or args.retries<1 or args.delay<0 or args.limit<0 or args.pdf_timeout<1:
        raise SystemExit('Numeric options are out of range.')
    end=args.end or datetime.now(KST).date()
    start=args.start or (end-timedelta(days=args.lookback_days-1) if args.mode=='daily' else months_before(end,args.months))
    if start>end: raise SystemExit('--start must be on or before --end')
    if args.run_id and not re.fullmatch(r'[0-9]{8}_[0-9]{6}_[a-z0-9]{6,32}',args.run_id):
        raise SystemExit('--run-id must use YYYYMMDD_HHMMSS_identifier format')
    args.output=args.output.resolve(); args.state_dir=args.state_dir.resolve()
    args.log_dir=(args.log_dir or args.state_dir/'logs').resolve()
    urls=dict(START_URLS)
    if args.urls_json:
        urls.update(json.loads(args.urls_json.read_text(encoding='utf-8-sig')))
    args.state_dir.mkdir(parents=True,exist_ok=True)
    run_id=args.run_id or datetime.now(KST).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    run_log,run_report,latest_report=run_artifact_paths(args.log_dir,run_id)
    configure_logging(args.state_dir,run_log)
    LOG.info('Run=%s mode=%s dates=%s..%s houses=%s output=%s',
             run_id,args.mode,start,end,','.join(args.houses),args.output)
    with run_lock(args.state_dir):
        state=State(args.state_dir)
        for house in HOUSES: (args.output/house).mkdir(parents=True,exist_ok=True)
        if args.mode=='status':
            state.export()
            rows=state.db.execute('SELECT house,status,count(*) AS count FROM reports GROUP BY house,status').fetchall()
            status_rows=[dict(r) for r in rows]
            LOG.info('Status rows=%s',json.dumps(status_rows,ensure_ascii=False))
            print(json.dumps(status_rows,ensure_ascii=False,indent=2)); state.db.close(); return 0
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise SystemExit('Install dependencies first: python -m pip install -r requirements_macro.txt')
        with sync_playwright() as pw:
            attached=bool(args.cdp_url)
            if attached:
                browser=pw.chromium.connect_over_cdp(args.cdp_url)
                if not browser.contexts: raise SystemExit('No Chrome context is available at that endpoint.')
                context=browser.contexts[0]
            else:
                profile=(args.profile_dir or args.state_dir/'chrome-profile').resolve()
                try:
                    context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',
                        headless=args.headless and args.mode!='login',accept_downloads=True,viewport={'width':1440,'height':1000})
                except Exception as exc:
                    raise SystemExit('Could not start Chrome. Check Chrome installation and that this automation profile is not already open. '+str(exc).splitlines()[0])
            context.set_default_navigation_timeout(60000)
            context.on('dialog',dismiss_dialog_safely)
            if args.minimize_window:
                context.on('page',lambda page:minimize_page_in_collector(context,page))
            try:
                if args.mode=='login':
                    login_pages=[]
                    for house in args.houses:
                        page=context.new_page(); login_pages.append(page)
                        try: page.goto(urls[house],wait_until='domcontentloaded')
                        except Exception: LOG.info('[%s] Complete login in Chrome.',house)
                    print('\n각 사이트에서 직접 로그인하고 검색 목록을 확인하세요. 파일은 다운로드하지 않습니다.')
                    input('로그인을 마쳤으면 이 창에서 Enter: ')
                    for page in login_pages:
                        if not page.is_closed(): page.close()
                    return 0
                started=datetime.now(KST).isoformat()
                state.db.execute('INSERT INTO runs(run_id,started,mode,start_date,end_date) VALUES(?,?,?,?,?)',
                    (run_id,started,args.mode,str(start),str(end))); state.db.commit()
                collector=Collector(context,args,state,start,end,urls)
                def checkpoint(summary,final):
                    finished=datetime.now(KST).isoformat() if final else None
                    if final: state.export()
                    state.db.execute('UPDATE runs SET finished=?,summary=? WHERE run_id=?',
                        (finished,json.dumps(summary,ensure_ascii=False),run_id)); state.db.commit()
                    overall=('complete' if all(x['status'] in ('complete','scan_complete') for x in summary.values())
                             else 'incomplete') if final else 'running'
                    report={'run_id':run_id,'mode':args.mode,'start':str(start),'end':str(end),
                            'started':started,'finished':finished,'overall_status':overall,
                            'output':str(args.output),'log':str(run_log),'houses':summary}
                    atomic_write_json(run_report,report)
                    atomic_write_json(latest_report,report)
                    if final:
                        LOG.info('Run=%s finished status=%s report=%s',run_id,overall,run_report)
                        print(json.dumps(report,ensure_ascii=False,indent=2))
                summary=run_requested_houses(collector,args.houses,checkpoint)
                return 2 if any(x['status']=='incomplete' for x in summary.values()) else 0
            finally:
                state.db.close()
                if not attached: context.close()


if __name__=='__main__':
    try:
        exit_code=main()
    except SystemExit as exc:
        if exc.code not in (None,0):
            LOG.error('Collector stopped before normal completion: %s',exc)
        raise
    except BaseException:
        LOG.exception('Collector terminated unexpectedly')
        raise
    raise SystemExit(exit_code)
