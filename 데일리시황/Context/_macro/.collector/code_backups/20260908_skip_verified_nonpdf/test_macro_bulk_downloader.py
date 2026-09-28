"""Offline tests. All browser requests are intercepted; no broker is contacted."""
import base64
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import macro_bulk_downloader as m


def sample_pdf():
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>']
    raw=b'%PDF-1.4\n'; offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(raw)); raw+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(raw)
    raw+=b'xref\n0 4\n0000000000 65535 f \n'
    raw+=b''.join(f'{n:010d} 00000 n \n'.encode() for n in offsets[1:])
    return raw+f'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


PDF=sample_pdf()


def report(house='HSBC',ident='123',day='07-Sep-26'):
    return m.Report(house,ident,'Macro: growth / rates?',day,'https://fixture.test/report','https://fixture.test/list')


class CoreTests(unittest.TestCase):
    def test_nine_calendar_months_and_leap_day(self):
        self.assertEqual(m.months_before(date(2026,9,7),9),date(2025,12,7))
        self.assertEqual(m.months_before(date(2024,3,31),1),date(2024,2,29))
        self.assertEqual(m.months_before(date(2025,3,31),1),date(2025,2,28))

    def test_publication_dates(self):
        for s in ['07-Sep-26','7 Sep 2026','Sep 07, 2026 5:03AM KST','2026-09-07T03:00:00Z']:
            self.assertEqual(m.parse_date(s),date(2026,9,7),s)
        self.assertEqual(m.parse_date('2 hours ago',datetime(2026,9,7,1,tzinfo=m.KST)),date(2026,9,6))
        self.assertIsNone(m.parse_date('2026-02-31'))
        self.assertIsNone(m.parse_date('no publication date'))

    def test_filename_safe_unique_and_deterministic(self):
        a=m.safe_filename('CON /<>:*? 한글','id1',date(2026,9,7))
        self.assertFalse(any(c in a for c in '<>:"/\\|?*'))
        self.assertNotEqual(a,m.safe_filename('CON /<>:*? 한글','id2',date(2026,9,7)))
        self.assertEqual(a,m.safe_filename('CON /<>:*? 한글','id1',date(2026,9,7)))

    def test_login_html_and_truncation_are_rejected(self):
        self.assertTrue(m.is_pdf(PDF))
        self.assertFalse(m.is_pdf(b'<html>login</html>'+b' '*500))
        self.assertFalse(m.is_pdf(PDF[:-20]))

    def test_jpm_original_search_is_valid(self):
        encoded=parse_qs(urlsplit(m.START_URLS['JPM']).query)['query'][0]
        query=parse_qs(base64.b64decode(encoded,validate=True).decode())
        filt=json.loads(query['customQueries'][0])
        self.assertEqual(filt['queries'][0]['displayName'],'Economics Commetary')
        def check(node):
            if isinstance(node,dict):
                if 'item' in node: self.assertIn('operator',node)
                for v in node.values(): check(v)
            elif isinstance(node,list):
                for v in node: check(v)
        check(filt)

    def test_cutoff_ignores_one_pinned_old_item(self):
        old=report(ident='old',day='06-Dec-25'); new=report()
        self.assertFalse(m.all_before([old,new],date(2025,12,7)))
        self.assertFalse(m.all_before([],date(2025,12,7)))
        self.assertTrue(m.all_before([old],date(2025,12,7)))

    def test_state_is_scoped_to_house_and_checks_file_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); state=m.State(root/'state'); saver=m.PDFSaver(None,root/'out')
            try:
                r=report(); state.record(r)
                path=saver.save(r,PDF); state.result(r,'downloaded',path=path,raw=PDF)
                self.assertTrue(state.downloaded(r))
                self.assertEqual(path.parent.name,'HSBC')
                same_other=report('GS'); state.record(same_other)
                self.assertFalse(state.downloaded(same_other))
                path.write_bytes(PDF.replace(b'200 200',b'300 300'))
                self.assertFalse(state.downloaded(r))
                path.unlink(); self.assertFalse(state.downloaded(r))
                state.export(); self.assertTrue((root/'state'/'manifest.csv').exists())
            finally: state.db.close()

    def test_scan_never_downloads_and_range_is_inclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            args=m.parser().parse_args(['--output',temp,'--mode','scan'])
            state=m.State(Path(temp)/'state')
            try:
                c=m.Collector(None,args,state,date(2025,12,7),date(2026,9,7),m.START_URLS)
                c.saver.download=Mock(side_effect=AssertionError('scan must not download'))
                rows=[report(ident='start',day='07-Dec-25'),report(ident='end'),
                      report(ident='old',day='06-Dec-25'),report(ident='future',day='08-Sep-26')]
                c.consume(rows,None); c.consume(rows,None)
                self.assertEqual(c.counts['HSBC']['listed'],2)
                self.assertEqual(c.counts['HSBC']['outside_range'],2)
                c.saver.download.assert_not_called()
            finally: state.db.close()

    def test_download_failures_cannot_be_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            args=m.parser().parse_args(['--output',temp,'--mode','backfill','--retries','1','--delay','0'])
            state=m.State(Path(temp)/'state')
            try:
                c=m.Collector(Mock(),args,state,date(2025,12,7),date(2026,9,7),m.START_URLS)
                c.saver.download=Mock(side_effect=ValueError('login page'))
                c.hsbc=lambda page:c.consume([report()],page)
                self.assertEqual(c.run_house('HSBC')['status'],'incomplete')
                self.assertEqual(state.db.execute('select status from reports').fetchone()[0],'failed')
            finally: state.db.close()


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(channel='chrome',headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(accept_downloads=True)
        self.context.route('**/*',lambda route: route.fulfill(status=200,content_type='text/html',body='<html>fixture</html>'))
        self.page=self.context.new_page(); self.page.goto('https://fixture.test/list')

    def tearDown(self):
        self.context.close()

    def test_five_report_lists_include_only_visible_relevant_rows(self):
        fixtures={
          'HSBC':'''<table id="allReportsTable"><tr class="reportTableRow"><td class="pubdateTableCell">07-Sep-26</td><td class="titleTableCell"><a href="/R/10/abc">Macro</a><div>Subtitle</div></td></tr></table><table id="keyReportsTable"><tr class="reportTableRow"><td class="pubdateTableCell">01-Jan-20</td><td class="titleTableCell"><a href="/R/10/hidden">Hidden key report</a></td></tr></table>''',
          'GS':'''<table><tr><td><a href="/content/research/en/reports/2026/09/07/abc.html">Macro</a></td><td>7 Sep 2026</td></tr><tr style="display:none"><td><a href="/content/research/en/reports/hidden.html">Hidden</a></td></tr></table>''',
          'JPM':'''<ul><li><a id="GPS-123-0" href="/research/content/GPS-123">Macro</a><p>Meeting 01 Jan 2026</p><time>07 Sep 2026</time></li></ul>''',
          'Citi':'''<div class="article-item-body"><a href="/cv2/smartlink/research/123?menuCode=MarketBuzz_OV">Macro</a><time>Sep 07, 2026 5:03AM KST</time></div>''',
          'BofA':'''<table><tr><td>07-Sep-2026</td><td><a id="portlet_123" onclick="htmlIconClickOnCachedPortlet('123','portlet_')"><span class="bold-text">Macro</span><span style="display:none">Do not duplicate title</span></a> Subtitle</td></tr></table><table style="display:none"><tr><td><a id="portlet_999" onclick="htmlIconClickOnCachedPortlet('999','portlet_')">Hidden region</a></td></tr></table>'''
        }
        for house,html in fixtures.items():
            with self.subTest(house=house):
                self.page.set_content(html)
                rows=m.extract(self.page.main_frame,house,self.page.url)
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0].published,'2026-09-07')
                self.assertIn('Macro',rows[0].title)
                if house=='JPM': self.assertEqual(rows[0].doc_id,'GPS-123')
                if house=='BofA': self.assertEqual(rows[0].title,'Macro — Subtitle')

    def test_native_download_from_pdf_button(self):
        def route_handler(route):
            if route.request.url.endswith('/original.pdf'):
                route.fulfill(content_type='application/pdf',headers={'Content-Disposition':'attachment; filename="original.pdf"'},body=PDF)
            else:
                route.fulfill(content_type='text/html',body='<button onclick="location.href=\'/original.pdf\'">Download PDF</button>')
        self.context.unroute('**/*'); self.context.route('**/*',route_handler)
        with tempfile.TemporaryDirectory() as temp:
            saver=m.PDFSaver(self.context,Path(temp),timeout=5)
            self.assertEqual(saver.download(report('GS'),self.page),PDF)
            self.assertEqual(len(self.context.pages),1)

    def test_citi_print_pdf_and_popup_download(self):
        def route_handler(route):
            if route.request.url.endswith('/original.pdf'):
                route.fulfill(content_type='application/pdf',headers={'Content-Disposition':'attachment'},body=PDF)
            else:
                route.fulfill(content_type='text/html',body='''<a id="printTabButton" href="#" onclick="document.getElementById('printPDF').hidden=false">Print</a><div id="printPDF" hidden><div role="button" aria-label="Print (PDF - 1 pages)" onclick="window.open('/original.pdf')">Print</div></div>''')
        self.context.unroute('**/*'); self.context.route('**/*',route_handler)
        with tempfile.TemporaryDirectory() as temp:
            saver=m.PDFSaver(self.context,Path(temp),timeout=5)
            self.assertEqual(saver.download(report('Citi'),self.page),PDF)

    def test_login_html_is_not_saved_with_pdf_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            saver=m.PDFSaver(self.context,Path(temp),timeout=1)
            with self.assertRaises(m.Incomplete): saver.download(report('GS'),self.page)
            self.assertEqual(list(Path(temp).rglob('*.pdf')),[])

    def test_bofa_list_click_popup_capture(self):
        def route_handler(route):
            if route.request.url.endswith('/original.pdf'):
                route.fulfill(content_type='application/pdf',headers={'Content-Disposition':'attachment'},body=PDF)
            else:
                route.fulfill(content_type='text/html',body='<button onclick="location.href=\'/original.pdf\'">Download PDF</button>')
        self.context.unroute('**/*'); self.context.route('**/*',route_handler)
        self.page.set_content('<a id="bofa-report" href="#" onclick="window.open(\'/report\')">Report</a>')
        with tempfile.TemporaryDirectory() as temp:
            saver=m.PDFSaver(self.context,Path(temp),timeout=5)
            raw=saver.download(report('BofA'),self.page,lambda:self.page.locator('#bofa-report').click())
            self.assertEqual(raw,PDF)
            self.assertEqual(len(self.context.pages),1)

    def test_missing_next_does_not_claim_advertised_total(self):
        self.page.set_content('<table><tr><td><a href="/content/research/en/reports/abc.html">Macro</a></td><td>07 Sep 2026</td></tr></table>')
        with tempfile.TemporaryDirectory() as temp:
            args=m.parser().parse_args(['--output',temp,'--delay','0'])
            state=m.State(Path(temp)/'state')
            try:
                c=m.Collector(self.context,args,state,date(2025,12,7),date(2026,9,7),m.START_URLS)
                with self.assertRaises(m.Incomplete):
                    c.paginated(self.page,'GS',self.page.main_frame,lambda:self.page.get_by_role('button',name='Next'),advertised_total=100)
            finally: state.db.close()

    def test_pagination_follows_real_next_and_stops_at_old_page(self):
        second='''<table><tr><td><a href="/content/research/en/reports/old.html">Old</a></td><td>01 Dec 2025</td></tr></table>'''
        self.page.set_content('''<table><tr><td><a href="/content/research/en/reports/new.html">New</a></td><td>07 Sep 2026</td></tr></table><button id="next">Next</button>''')
        self.page.locator('#next').evaluate('(button,html)=>button.onclick=()=>document.body.innerHTML=html',second)
        with tempfile.TemporaryDirectory() as temp:
            args=m.parser().parse_args(['--output',temp,'--delay','0'])
            state=m.State(Path(temp)/'state')
            try:
                c=m.Collector(self.context,args,state,date(2025,12,7),date(2026,9,7),m.START_URLS)
                total,reason=c.paginated(self.page,'GS',self.page.main_frame,lambda:self.page.get_by_role('button',name='Next'))
                self.assertEqual((total,reason),(2,'cutoff'))
                self.assertEqual(c.counts['GS']['listed'],1)
            finally: state.db.close()


if __name__=='__main__':
    unittest.main(verbosity=2)
