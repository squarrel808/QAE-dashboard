"""Bounded live list verification; owns one tab, never saves reports or state."""
from datetime import date
import argparse
import logging
from playwright.sync_api import sync_playwright
import macro_bulk_downloader as m
import run_macro_separate_chrome as launcher


class ReadOnlyCollector(m.Collector):
    def consume(self,rows,page):
        for row in rows:
            assert self.start<=date.fromisoformat(row.published)<=self.end
            self.seen.add((row.house,row.doc_id))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--start',type=date.fromisoformat,default=date(2026,8,24))
    parser.add_argument('--end',type=date.fromisoformat,default=date(2026,9,9))
    probe_args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    assert launcher.verify_owner(), 'Dedicated port 9223 is not verified'
    args=m.parser().parse_args(['--mode','scan','--delay','0'])
    with sync_playwright() as pw:
        browser=pw.chromium.connect_over_cdp(launcher.CDP)
        page=browser.contexts[0].new_page()
        try:
            collector=ReadOnlyCollector(browser.contexts[0],args,None,probe_args.start,probe_args.end,m.START_URLS)
            collector.hsbc(page)
            print('Verified distinct HSBC list records: '+str(len(collector.seen)),flush=True)
            print(page.evaluate("""() => ({
              paging:document.querySelector('#allReportsPageNumbers')?.innerText,
              nodes:[...document.querySelectorAll('#allReportsPageNumbers *,#allReports .npLink')].map(e=>({tag:e.tagName,cls:e.className,text:e.innerText,visible:!!e.getClientRects().length})),
              noReports:[...document.querySelectorAll('#allReportsTable #noReportsCell')].map(e=>({text:e.innerText,visible:!!e.getClientRects().length}))
            })"""),flush=True)
        except Exception:
            print(page.evaluate("""() => ({
              table:!!document.querySelector('#allReportsTable'),
              visible:!!document.querySelector('#allReportsTable')?.getClientRects().length,
              dates:['datespecific','datefromday','datefrommonth','datetoday','datetomonth'].map(k=>new URLSearchParams(document.querySelector('#allReportsSortDateURL')?.value||'').get(k)),
              panel:document.querySelector('#allReports')?.innerText?.slice(0,200),
              titles:[...document.querySelectorAll('h1,h2')].map(e=>e.innerText),
              body:document.body.innerText.slice(0,1000)
            })"""),flush=True)
            raise
        finally:
            page.close()


if __name__=='__main__':
    main()
