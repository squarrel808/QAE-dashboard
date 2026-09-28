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
            "SELECT status FROM reports WHERE house=? AND doc_id=?", (r.house, r.doc_id)
        ).fetchone()
        return bool(row and row['status'] == 'no_original_pdf')

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

    def download(self, r: Report, source_page, click=None) -> bytes:
        # JPM's direct route is also used by the user's existing QAE downloader.
        direct = r.url if r.house == "HSBC" else ""
        if r.house == "JPM":
            direct = f"https://markets.jpmorgan.com/research/ArticleServlet?doc={r.doc_id}.pdf"
        if direct:
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
            try:
                if click:
                    click()
                else:
                    work.goto(r.url, wait_until="domcontentloaded",timeout=45000)
            except Exception:
                # A real attachment aborts normal navigation; process the download event.
                pass
            deadline = time.monotonic() + self.timeout
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
                                control = visible(frame.get_by_role("button",name=re.compile(r"^Print \(PDF")))
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
                if not any(not p.is_closed() for p in owned):
                    source_page.wait_for_timeout(250)
            raise Incomplete("Original PDF did not arrive; check login, entitlement, or PDF button. HTML was not saved as PDF.")
        finally:
            self.context.remove_listener("page",on_page)
            for page in watched:
                try:
                    page.remove_listener("download",on_download)
                    page.remove_listener("response",on_response)
                except Exception:
                    pass
            for page in owned:
                if not page.is_closed():
                    page.close()


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
            click = None
            if r.house == "BofA":
                # Exact current-list element; no guessed report URL or dynamic function execution.
                click = lambda ident=r.element_id: page.locator('[id='+json.dumps(ident)+']').click(timeout=10000)
            for attempt in range(self.args.retries):
                try:
                    raw=self.saver.download(r,page,click)
                    path=self.saver.save(r,raw)
                    self.state.result(r,"downloaded",path=path,raw=raw)
                    count["downloaded"]+=1
                    LOG.info("[%s] saved %s (%s KB)",r.house,path.name,len(raw)//1024)
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
        seen_pages=set(); total=0
        for page_no in range(1,self.args.max_pages+1):
            rows=extract(frame,house,page.url,region)
            if not rows:
                raise Incomplete("Empty or unreadable report list. Login or search results need verification.")
            sig=signature(rows)
            if sig in seen_pages:
                raise Incomplete("Pagination repeated a page; refusing to claim complete history.")
            seen_pages.add(sig); total+=len(rows)
            LOG.info("[%s%s] page %s, %s rows, oldest=%s",house,':'+region if region else '',page_no,len(rows),min((r.published or 'unknown') for r in rows))
            self.consume(rows,page)
            if all_before(rows,floor):
                return total,"cutoff"
            button=visible(next_locator())
            if not button:
                if advertised_total is not None and total<advertised_total:
                    raise Incomplete(f'Next page is unavailable after {total} rows, but the site advertises {advertised_total} documents.')
                if house=='HSBC':
                    paging=frame.locator('#allReportsPageNumbers')
                    current=paging.locator('.current_page')
                    if current.count():
                        numbers=[int(n) for n in re.findall(r'\b\d+\b',paging.inner_text())]
                        if numbers and max(numbers)>int(current.inner_text().strip()):
                            raise Incomplete('HSBC still advertises later pages, but Next is unavailable.')
                if house=='JPM':
                    position=re.search(r'Page\s+(\d+)\s+of\s+(\d+)',frame.locator('body').inner_text(),re.I)
                    if position and int(position[1])<int(position[2]):
                        raise Incomplete('JPM still advertises later pages, but Next is unavailable.')
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
        page.goto(self.urls['JPM'],wait_until="domcontentloaded")
        frame=frame_with(page,'a[href*="/research/content/GPS-"]')
        self.paginated(page,'JPM',frame,lambda:frame.get_by_role('button',name='Next Page',exact=True))

    def hsbc(self,page):
        # The legacy list has a server-side result cap. Weekly slices are split again if necessary.
        slices=[]; current=self.start
        while current<=self.end:
            stop=min(self.end,current+timedelta(days=6)); slices.append((current,stop)); current=stop+timedelta(days=1)
        while slices:
            start,end=slices.pop()
            page.goto(self.urls['HSBC'],wait_until="domcontentloaded")
            frame_with(page,'#mainFilters')
            if not page.locator('#mainFilters').is_visible():
                page.get_by_text('Advanced Search',exact=True).click()
            page.locator('#mainFilters').select_option('8')
            dialog=page.get_by_role('dialog')
            dialog.get_by_role('radio',name='Between',exact=True).check()
            for field,day in [('#dateFromDisp',start),('#dateToDisp',end)]:
                select_hsbc_date(page,field,day)
            dialog.get_by_role('link',name='Select',exact=True).click()
            page.get_by_role('link',name='Search',exact=True).click()
            def ready():
                rows=extract(page.main_frame,'HSBC',page.url)
                body=page.locator('body').inner_text()
                if not rows and re.search(r'No (reports|results|records|documents)',body,re.I):
                    return "empty"
                if rows and all(r.published and start<=date.fromisoformat(r.published)<=end for r in rows):
                    return rows
                return None
            loaded=wait_until(ready,45)
            if loaded=='empty':
                continue
            total,reason=self.paginated(page,'HSBC',page.main_frame,lambda:page.locator('.npLink').filter(has_text=re.compile(r'^\s*Next\s*$')),start=start)
            if total>=75 and reason=='end':
                if start==end:
                    raise Incomplete(f"HSBC returned at least 75 rows for {start}; possible result cap. Narrow further on the site.")
                middle=start+(end-start)//2
                slices.extend([(start,middle),(middle+timedelta(days=1),end)])

    def bofa(self,page):
        regions={'Global':'Global','US/Can':'North America','Eur':'Europe','Jpn':'Japan','Aus/NZ':'Aus/NZ'}
        for region,search_region in regions.items():
            page.goto(self.urls['BofA'],wait_until="domcontentloaded")
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
        page=self.context.new_page(); page.set_default_timeout(12000)
        try:
            getattr(self,house.lower())(page)
            counts=self.counts[house]
            if counts['failed'] or counts['unknown_date']:
                return {'status':'incomplete','reason':'Failed PDFs or unparseable publication dates remain.','counts':dict(counts)}
            return {'status':'scan_complete' if self.args.mode=='scan' else 'complete','counts':dict(counts)}
        except Exception as exc:
            LOG.error('[%s] incomplete: %s',house,exc)
            return {'status':'incomplete','reason':str(exc)[:600],'counts':dict(self.counts[house])}
        finally:
            if not page.is_closed(): page.close()
            self.state.export()


def parser():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--mode',choices=['scan','backfill','daily','login','status'],default='scan')
    p.add_argument('--houses',nargs='+',choices=HOUSES,default=list(HOUSES))
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--state-dir',type=Path,default=Path(__file__).resolve().parent/'.collector')
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
    p.add_argument('--urls-json',type=Path,help='Optional house-to-start-URL overrides after a site changes')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.months<1 or args.lookback_days<1 or args.max_pages<1 or args.retries<1 or args.delay<0 or args.limit<0 or args.pdf_timeout<1:
        raise SystemExit('Numeric options are out of range.')
    end=args.end or datetime.now(KST).date()
    start=args.start or (end-timedelta(days=args.lookback_days-1) if args.mode=='daily' else months_before(end,args.months))
    if start>end: raise SystemExit('--start must be on or before --end')
    args.output=args.output.resolve(); args.state_dir=args.state_dir.resolve()
    urls=dict(START_URLS)
    if args.urls_json:
        urls.update(json.loads(args.urls_json.read_text(encoding='utf-8-sig')))
    args.state_dir.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(),logging.FileHandler(args.state_dir/'collector.log',encoding='utf-8')])
    with run_lock(args.state_dir):
        state=State(args.state_dir)
        for house in HOUSES: (args.output/house).mkdir(parents=True,exist_ok=True)
        if args.mode=='status':
            state.export()
            rows=state.db.execute('SELECT house,status,count(*) AS count FROM reports GROUP BY house,status').fetchall()
            print(json.dumps([dict(r) for r in rows],ensure_ascii=False,indent=2)); state.db.close(); return 0
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
                run_id=datetime.now(KST).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
                state.db.execute('INSERT INTO runs(run_id,started,mode,start_date,end_date) VALUES(?,?,?,?,?)',
                    (run_id,datetime.now(KST).isoformat(),args.mode,str(start),str(end))); state.db.commit()
                LOG.info('Mode=%s, dates=%s..%s, output=%s',args.mode,start,end,args.output)
                collector=Collector(context,args,state,start,end,urls)
                summary={}
                try:
                    for house in args.houses: summary[house]=collector.run_house(house)
                except KeyboardInterrupt:
                    summary['interrupted']={'status':'incomplete','reason':'Stopped by user; rerun the same command to resume.'}
                finally:
                    state.export()
                    state.db.execute('UPDATE runs SET finished=?,summary=? WHERE run_id=?',
                        (datetime.now(KST).isoformat(),json.dumps(summary,ensure_ascii=False),run_id)); state.db.commit()
                    report={'run_id':run_id,'mode':args.mode,'start':str(start),'end':str(end),'output':str(args.output),'houses':summary}
                    (args.state_dir/f'run_{run_id}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                    print(json.dumps(report,ensure_ascii=False,indent=2))
                return 2 if any(x['status']=='incomplete' for x in summary.values()) else 0
            finally:
                state.db.close()
                if not attached: context.close()


if __name__=='__main__':
    raise SystemExit(main())
