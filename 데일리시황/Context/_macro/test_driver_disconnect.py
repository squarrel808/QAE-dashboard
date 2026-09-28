"""Offline transport-loss and single-driver window-control regression tests."""
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import macro_bulk_downloader as m


class DriverDisconnectTests(unittest.TestCase):
    def test_dialog_race_is_caught_without_reading_dialog_content(self):
        dialog = Mock()
        dialog.dismiss.side_effect = RuntimeError('Protocol error (Page.handleJavaScriptDialog): No dialog is showing')
        m.dismiss_dialog_safely(dialog)
        dialog.dismiss.assert_called_once()
        self.assertNotIn('message', dialog.__dict__)

    def test_dialog_is_dismissed_once(self):
        dialog = Mock()
        m.dismiss_dialog_safely(dialog)
        dialog.dismiss.assert_called_once()

    def test_transport_error_does_not_call_close_and_still_exports(self):
        context, state, page = Mock(), Mock(), Mock()
        context.new_page.return_value = page
        context.browser.is_connected.return_value = True
        args = SimpleNamespace(output=None, pdf_timeout=45, mode='backfill')
        collector = m.Collector(context,args,state,date(2026,6,8),date(2026,9,9),m.START_URLS)
        collector.gs = Mock(side_effect=RuntimeError('Locator.count: Connection closed while reading from the driver'))
        result = collector.run_house('GS')
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(result['connection_lost'])
        page.close.assert_not_called()
        state.export.assert_called_once()

    def test_disconnected_browser_does_not_receive_minimize_commands(self):
        context, page = Mock(), Mock()
        context.browser.is_connected.return_value = False
        page.is_closed.return_value = False
        m.minimize_page_in_collector(context,page)
        context.new_cdp_session.assert_not_called()

    def test_minimize_uses_the_same_context_and_detaches(self):
        context, page = Mock(), Mock()
        context.browser.is_connected.return_value = True
        page.is_closed.return_value = False
        session = context.new_cdp_session.return_value
        session.send.return_value = {'windowId': 42}
        m.minimize_page_in_collector(context,page)
        context.new_cdp_session.assert_called_once_with(page)
        session.send.assert_any_call('Browser.setWindowBounds',
                                    {'windowId':42,'bounds':{'windowState':'minimized'}})
        session.detach.assert_called_once()

    def test_driver_loss_finalizes_current_and_unstarted_houses(self):
        collector = Mock()
        collector.counts = {'GS':{},'Citi':{}}
        collector.run_house.return_value = {'status':'incomplete','counts':{},'connection_lost':True}
        snapshots = []
        result = m.run_requested_houses(collector,['GS','Citi'],lambda summary,final:snapshots.append(final))
        collector.run_house.assert_called_once_with('GS')
        self.assertTrue(snapshots[-1])
        self.assertEqual(result['Citi']['status'],'incomplete')


if __name__ == '__main__':
    unittest.main()
