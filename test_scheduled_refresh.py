import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scheduled_refresh as scheduled
import deploy_check

class ScheduledRefreshTests(unittest.TestCase):
    def test_live_check_encodes_korean_weekly_paths(self):
        with patch.object(deploy_check.urllib.request,'urlopen') as opened:
            opened.return_value.__enter__.return_value.read.return_value=b'ok'
            self.assertEqual(deploy_check.fetch_bytes('weekly/주간 시황.html','test'),b'ok')
            url=opened.call_args.args[0].full_url
            self.assertIn('/weekly/%EC%A3%BC%EA%B0%84%20',url)
            self.assertTrue(url.isascii())

    def test_failed_module_restores_partial_outputs_and_next_module_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            public=Path(directory)
            (public/'data').mkdir()
            (public/'data/a.json').write_text('{"old":1}')
            def fail(run_id,*args):
                (public/'data/a.json').write_text('broken')
                (public/'data/new.json').write_text('{}')
                raise RuntimeError('fetch failed')
            with patch.object(scheduled.runner,'log'):
                result=scheduled.refresh_module(('failed',[('fetch.py',)],['data'],[]),'test',execute=fail,public=public)
            self.assertEqual(result['status'],'failed')
            self.assertEqual(json.loads((public/'data/a.json').read_text()),{'old':1})
            self.assertFalse((public/'data/new.json').exists())
            def good(run_id,*args):(public/'data/b.json').write_text('{}')
            result=scheduled.refresh_module(('next',[('fetch.py',)],['data/b.json'],[]),'test',execute=good,public=public)
            self.assertEqual(result['status'],'updated')

    def test_independent_publish_checks_nested_files_and_weekly(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);public=root/'macro_hub/public'
            for relative in ['data/example.json','embeds/country-indicators/index.html','weekly/AI/report.html']:
                path=public/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
            marker=deploy_check.prepare('test',root,validate_reports_now=False)
            self.assertEqual(len(marker['files']),3)
            self.assertTrue(deploy_check.verify(marker,timeout=0,log=lambda _:None,fetch=lambda name,_:(public/name).read_bytes()))
            (public/'data/policy.json').write_text('{"held":true}')
            marker=deploy_check.prepare('held',root,validate_reports_now=False,excluded_paths=scheduled.HELD_OUTPUTS)
            self.assertNotIn('data/policy.json',marker['files'])

    def test_all_automatic_screens_included_without_policy_execution(self):
        names={module[0] for module in scheduled.MODULES}
        self.assertTrue({'PMI','Theme','Factor','CPI 분포','PCA I','PCA II·III·국가별 경제지표','Context Macro'}.issubset(names))
        for _,steps,_,_ in scheduled.MODULES:
            for step in steps:
                self.assertNotIn('policy',step[0].lower())
                self.assertNotIn('extract_houseviews',step[0])
                self.assertTrue((scheduled.ROOT/step[0]).is_file(),step[0])

if __name__=='__main__':unittest.main()
