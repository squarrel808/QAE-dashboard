"""Offline browser regressions for HSBC's two asynchronous report panels."""
import html
import unittest
from datetime import date

from playwright.sync_api import sync_playwright
import macro_bulk_downloader as m


class HSBCReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(channel='chrome',headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.page=self.browser.new_page()
        self.start,self.end=date(2026,8,31),date(2026,9,6)

    def tearDown(self):
        self.page.close()

    def fixture(self, *, rows=True, query=True, empty=False, key_empty=False, wrong_query=False):
        q='datespecific=between&datefromday=31&datefrommonth=202608&datetoday=06&datetomonth=202609'
        if wrong_query:
            q='datespecific=all'
        content='<div id="allReports">'
        if query:
            content+='<input id="allReportsSortDateURL" type="hidden" value="'+html.escape(q)+'">'
        content+='<table id="allReportsTable">'
        if rows:
            content+='<tr class="reportTableRow"><td class="pubdateTableCell">04-Sep-26</td><td class="titleTableCell"><a href="https://fixture.test/report">Macro</a></td></tr>'
        if empty:
            content+='<tr><td id="noReportsCell">No Reports Found</td></tr>'
        content+='</table></div>'
        if key_empty:
            content+='<div id="keyReports"><table><tr><td id="noReportsCell">No Reports Found</td></tr></table></div>'
        self.page.set_content(content)

    def test_unrelated_empty_panel_cannot_complete_loading_search(self):
        self.fixture(rows=False,key_empty=True)
        self.assertIsNone(m.hsbc_results_ready(self.page,self.start,self.end))

    def test_old_matching_rows_do_not_complete_unapplied_date_filter(self):
        self.fixture(wrong_query=True)
        self.assertIsNone(m.hsbc_results_ready(self.page,self.start,self.end))
        self.assertEqual(len(m.hsbc_results_ready(self.page)),1)

    def test_result_must_match_both_date_endpoints(self):
        self.fixture()
        self.assertEqual(len(m.hsbc_results_ready(self.page,self.start,self.end)),1)
        self.assertIsNone(m.hsbc_results_ready(self.page,self.start,date(2026,9,7)))

    def test_genuine_empty_result_is_accepted_only_for_its_date_range(self):
        self.fixture(rows=False,empty=True)
        self.assertEqual(m.hsbc_results_ready(self.page,self.start,self.end),'empty')
        self.assertIsNone(m.hsbc_results_ready(self.page,date(2026,8,24),date(2026,8,30)))

    def test_hidden_all_reports_is_not_ready(self):
        self.fixture()
        self.page.locator('#allReports').evaluate("e=>e.style.display='none'")
        self.assertIsNone(m.hsbc_results_ready(self.page,self.start,self.end))


if __name__=='__main__':
    unittest.main(verbosity=2)
