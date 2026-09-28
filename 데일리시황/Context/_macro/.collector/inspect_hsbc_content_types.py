"""Read visible content markers in owned tabs on the verified isolated macro browser."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_macro_separate_chrome as launcher
from playwright.sync_api import sync_playwright


def inspect():
    if not launcher.verify_owner():
        raise SystemExit('Isolated Chrome is not running; no browser was launched.')
    sources = [
        'https://www.research.hsbc.com/O/24lNTWShrCxjQZ',
        'https://www.research.hsbc.com/R/10/dmDn6DSCxjQZ',
    ]
    with sync_playwright() as pw:
        context = pw.chromium.connect_over_cdp(launcher.CDP).contexts[0]
        for url in sources:
            page = context.new_page()
            try:
                response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(1800)
                frames = []
                for frame in page.frames:
                    parts = urlsplit(frame.url)
                    info = frame.evaluate(r'''() => {
                      const visible = el => !!el.getClientRects().length;
                      const text = el => (el.innerText || '').trim();
                      return {
                        title:document.title, ready:document.readyState,
                        newsletter:{title:text(document.querySelector('#firstTitleBoxTitle')||document.createElement('div')),date:text(document.querySelector('#firstTitleBoxDate')||document.createElement('div')),focusCount:document.querySelectorAll('#researchFocusPortletContent .focusReport').length},
                        body:text(document.body).slice(0,900),
                        headings:[...document.querySelectorAll('h1,h2,h3')].filter(visible).map(el=>({tag:el.tagName,id:el.id,cls:el.className,text:text(el)})).slice(0,16),
                        controls:[...document.querySelectorAll('a,button,[role="button"]')].filter(visible).map(el=>({tag:el.tagName,id:el.id,cls:el.className,label:[text(el),el.getAttribute('title'),el.getAttribute('aria-label')].filter(Boolean).join(' | '),path:el.href?new URL(el.href,location.href).pathname:'',onclick:el.getAttribute('onclick')})).filter(el=>/pdf|download|print|video|podcast|play|full report|subscribe|unsubscribe/i.test(el.label)).slice(0,20),
                        media:[...document.querySelectorAll('video,audio,iframe,object,embed')].filter(visible).map(el=>({tag:el.tagName,id:el.id,cls:el.className,title:el.title||'',src:el.src?new URL(el.src,location.href).origin+new URL(el.src,location.href).pathname:''})),
                        content_ids:[...document.querySelectorAll('main,article,[id]')].filter(visible).map(el=>({tag:el.tagName,id:el.id,cls:el.className})).slice(0,50)
                      };
                    }''')
                    frames.append({'location':parts.netloc+parts.path,'dom':info})
                print(json.dumps({'source':url,'status':response.status if response else None,'frames':frames},ensure_ascii=False),flush=True)
            finally:
                if not page.is_closed():
                    page.close()


if __name__ == '__main__':
    inspect()
