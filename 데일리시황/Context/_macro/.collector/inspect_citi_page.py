"""Read visible Citi page diagnostics in the isolated macro browser only."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_macro_separate_chrome as launcher
from playwright.sync_api import sync_playwright

if not launcher.verify_owner():
    raise SystemExit('Isolated macro Chrome is unavailable.')
with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(launcher.CDP)
    pages = [p for p in browser.contexts[0].pages if 'citivelocity.com' in p.url]
    if not pages:
        raise SystemExit('No existing Citi tab.')
    page = pages[-1]
    print(json.dumps({'title': page.title(), 'frames': len(page.frames)}, ensure_ascii=True))
    for frame in page.frames:
        try:
            body = frame.locator('body').inner_text(timeout=4000)
            controls = frame.locator('button, [role=menuitem], input[placeholder], a').evaluate_all(
                "els => els.filter(e => e.getClientRects().length).slice(0, 55).map(e => ({tag:e.tagName,text:(e.innerText||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').trim().slice(0,120)}))")
            print(json.dumps({'body': body[:7000], 'controls': controls}, ensure_ascii=True))
        except Exception as exc:
            print(type(exc).__name__)
