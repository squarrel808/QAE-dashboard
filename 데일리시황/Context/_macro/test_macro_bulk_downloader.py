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
    def test_run_artifacts_are_grouped_by_day(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            log,report,latest=m.run_artifact_paths(root,'20260909_071500_abcdef')
            self.assertEqual(log.parent,root/'2026-09-09')
            self.assertEqual(log.name,'run_20260909_071500_abcdef.log')
            self.assertEqual(report.name,'run_20260909_071500_abcdef.json')
            self.assertEqual(latest,root/'latest_run.json')

    def test_atomic_json_replaces_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'latest_run.json'
            m.atomic_write_json(path,{'overall_status':'incomplete'})
            m.atomic_write_json(path,{'overall_status':'complete'})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['overall_status'],'complete')
            self.assertFalse(path.with_suffix('.json.tmp').exists())

    def test_confirmed_non_pdf_is_preserved_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            args=m.parser().parse_args(['--output',temp,'--mode','backfill'])
            state=m.State(Path(temp)/'state')
            try:
                r=report(); state.record(r)
                state.result(r,'no_original_pdf','Verified video; no standalone PDF.')
                c=m.Collector(None,args,state,date(2026,6,8),date(2026,9,8),m.START_URLS)
                c.saver.download=Mock(side_effect=AssertionError('Confirmed video must not be retried'))
                c.consume([r],None)
                c.saver.download.assert_not_called()
                self.assertEqual(c.counts['HSBC']['no_original_pdf'],1)
                self.assertTrue(state.known_no_original_pdf(r))
                other=report('GS'); state.record(other)
                self.assertFalse(state.known_no_original_pdf(other))
            finally:
                state.db.close()

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

    def test_missing_jpm_button_is_failed_and_next_report_downloads(self):
        with tempfile.TemporaryDirectory() as temp:
            args=m.parser().parse_args(['--output',temp,'--mode','backfill','--retries','1','--delay','0'])
            state=m.State(Path(temp)/'state')
            try:
                c=m.Collector(Mock(),args,state,date(2026,6,8),date(2026,9,8),m.START_URLS)
                missing=report('JPM','missing'); available=report('JPM','available')
                c.saver.download=Mock(return_value=PDF)
                c.jpm=lambda page:c.consume([missing,available],page)
                with patch.object(m,'frame_with',side_effect=[m.Incomplete('Missing download button'),Mock()]):
                    result=c.run_house('JPM')
                self.assertEqual(result['status'],'incomplete')
                self.assertEqual(result['counts']['failed'],1)
                self.assertEqual(result['counts']['downloaded'],1)
                rows=state.db.execute('SELECT doc_id,status,error FROM reports ORDER BY doc_id').fetchall()
                self.assertEqual([(r['doc_id'],r['status']) for r in rows],[('available','downloaded'),('missing','failed')])
                self.assertIn('Missing download button',rows[1]['error'])
                c.saver.download.assert_called_once()
            finally: state.db.close()

    def test_closed_browser_is_a_house_failure(self):
        args=m.parser().parse_args(['--mode','backfill'])
        context=Mock(); context.new_page.side_effect=RuntimeError('Browser has been closed')
        state=Mock()
        c=m.Collector(context,args,state,date(2026,6,8),date(2026,9,8),m.START_URLS)
        result=c.run_house('Citi')
        self.assertEqual(result['status'],'incomplete')
        self.assertIn('Browser has been closed',result['reason'])
        state.export.assert_called_once()

    def test_interrupt_preserves_finished_and_unstarted_house_snapshots(self):
        collector=Mock()
        collector.counts={house:{} for house in m.HOUSES}
        collector.run_house.side_effect=[{'status':'complete','counts':{'downloaded':2}},KeyboardInterrupt()]
        snapshots=[]
        checkpoint=lambda summary,final:snapshots.append((json.loads(json.dumps(summary)),final))
        result=m.run_requested_houses(collector,['JPM','HSBC','BofA'],checkpoint)
        self.assertEqual(result['JPM']['status'],'complete')
        self.assertEqual(result['HSBC']['status'],'incomplete')
        self.assertEqual(result['BofA']['status'],'incomplete')
        self.assertIn('interrupted',result)
        self.assertTrue(all(x['status']=='not_started' for x in snapshots[0][0].values()))
        self.assertEqual(snapshots[2][0]['JPM']['status'],'complete')
        self.assertEqual(snapshots[3][0]['HSBC']['status'],'running')
        self.assertEqual(snapshots[-1],(result,True))

    def test_unexpected_stop_writes_incomplete_report_for_every_requested_house(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            collector=Mock(); collector.counts={house:{} for house in m.HOUSES}
            collector.run_house.side_effect=[{'status':'complete','counts':{}},RuntimeError('Browser lost')]
            with patch('playwright.sync_api.sync_playwright') as playwright, \
                 patch.object(m,'Collector',return_value=collector), \
                 patch.object(m,'configure_logging'), patch('builtins.print'):
                browser=playwright.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value
                browser.contexts=[Mock()]
                with self.assertRaisesRegex(RuntimeError,'Browser lost'):
                    m.main(['--mode','backfill','--houses','JPM','HSBC','BofA','--start','2026-06-08',
                            '--end','2026-09-08','--output',str(root/'out'),'--state-dir',str(root/'state'),
                            '--cdp-url','http://fixture.invalid:9222'])
            latest=json.loads((root/'state/logs/latest_run.json').read_text(encoding='utf-8'))
            self.assertEqual(latest['overall_status'],'incomplete')
            self.assertIsNotNone(latest['finished'])
            self.assertEqual(set(latest['houses']),{'JPM','HSBC','BofA'})
            self.assertEqual(latest['houses']['JPM']['status'],'complete')
            self.assertEqual(latest['houses']['HSBC']['status'],'incomplete')
            self.assertIn('Browser lost',latest['houses']['HSBC']['reason'])
            self.assertEqual(latest['houses']['BofA']['status'],'incomplete')
            reports=list((root/'state/logs').glob('*/run_*.json'))
            self.assertEqual(len(reports),1)
            self.assertEqual(json.loads(reports[0].read_text(encoding='utf-8')),latest)


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

    def test_jpm_search_row_download_uses_native_button(self):
        def route_handler(route):
            if route.request.url.endswith('/original.pdf'):
                route.fulfill(content_type='application/pdf',headers={'Content-Disposition':'attachment; filename="original.pdf"'},body=PDF)
            else:
                route.fulfill(content_type='text/html',body='<button id="GPS-123-0" data-testid="download-button" onclick="location.href=\'/original.pdf\'">Download</button>')
        self.context.unroute('**/*'); self.context.route('**/*',route_handler)
        self.page.goto('https://fixture.test/list')
        with tempfile.TemporaryDirectory() as temp:
            saver=m.PDFSaver(self.context,Path(temp),timeout=5)
            saver.request_pdf=Mock(side_effect=AssertionError('The search button must not use a guessed direct URL'))
            click=lambda:self.page.locator('button[data-testid="download-button"]').click()
            self.assertEqual(saver.download(report('JPM','GPS-123-0'),self.page,click),PDF)
            saver.request_pdf.assert_not_called()

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
