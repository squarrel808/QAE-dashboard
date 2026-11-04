import copy
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import update_surprise as u
from portal_link import add_portal_link

class SurpriseTests(unittest.TestCase):
    def fixture(self):
        dates=['2026-10-19','2026-10-20','2026-10-21','2026-10-22','2026-10-23','2026-10-24','2026-10-26']
        rows=[dict(date=d,value=v,update_dt=d+'T01:00:00') for d,v in zip(dates,[1,2,3,4,5,999,6])]
        return {'source':'snowflake','source_table':'TAA_DB_DEV.CORE.FACT_TIME_SERIES','retrieved_at':'2026-10-26T21:00:00+09:00','start_date':'2020-01-01','cutoff':'2026-10-26',
                'economic':[{'meta':{'country_ISO':'US','country_KOR':'미국','ticker':'CESIUSD Index','series_id':5929,'provider':'HAVER'},'rows':rows}],
                'inflation':[{'meta':{'country_ISO':'US','country_KOR':'미국','descriptor':'Citigroup Inflation Surprise Index','ticker_pk':'g10:n111vcis','series_id':5930,'provider':'HAVER'},
                'rows':[{'date':f'2026-{i:02d}-28','value':i} for i in range(1,7)]}]}
    def test_rolling_and_monthly(self):
        d=u.prepare(self.fixture(),datetime(2026,10,26,tzinfo=u.KST))
        p=d['economic'][0]['points']
        self.assertEqual([x[2] for x in p],[None,None,None,None,3.0,4.0])
        self.assertEqual(d['economic'][0]['weekendsExcluded'],1)
        self.assertTrue(all(x[1]==x[2] for x in d['inflation'][0]['points']))
    def test_legacy_source_rejected(self):
        raw=self.fixture();raw.pop('source')
        with self.assertRaises(ValueError): u.prepare(raw,datetime(2026,10,27,tzinfo=u.KST))
    def test_revision_and_invalid_values(self):
        raw=self.fixture(); raw['economic'][0]['rows'].append({'date':'2026-10-19','value':11,'update_dt':'2026-10-20T03:00:00'})
        d=u.prepare(raw,datetime(2026,10,26,tzinfo=u.KST))
        self.assertEqual(d['economic'][0]['points'][4][2],5.0)
        raw['economic'][0]['rows'][0]['value']=None
        with self.assertRaises(ValueError): u.prepare(raw,datetime(2026,10,26,tzinfo=u.KST))
    def test_portal_idempotent(self):
        with TemporaryDirectory(dir=u.ROOT) as t:
            root=Path(t); (root/'surprise index').mkdir(); (root/'surprise index/index.html').write_text('ok')
            old='<main><a href="existing.html">기존</a></main>'
            new=add_portal_link(old,root/'index.html')
            self.assertIn('<a href="existing.html">기존</a>',new)
            self.assertEqual(new,add_portal_link(new,root/'index.html'))
    def test_failed_refresh_preserves_page(self):
        with TemporaryDirectory(dir=u.ROOT) as t:
            root=Path(t); (root/'index.html').write_text('previous')
            (root/'config.json').write_text('{}')
            with patch.object(u,'ROOT',root),patch.object(u,'fetch',side_effect=RuntimeError('API unavailable')):
                with self.assertRaises(RuntimeError): u.run(SimpleNamespace(from_cache=False,open=False))
            self.assertEqual((root/'index.html').read_text(),'previous')

    def test_real_portal_and_daily_renderer(self):
        import importlib.util
        from bs4 import BeautifulSoup
        latest=json.loads((u.ROOT/'latest.json').read_text(encoding='utf-8'))
        backups=list((u.ROOT/'runs').glob('*/portal_before.html'))
        before=BeautifulSoup(backups[0].read_text(encoding='utf-8'),'html.parser')
        after=BeautifulSoup((u.ROOT.parent/'index.html').read_text(encoding='utf-8'),'html.parser')
        links=lambda doc:{(a.get('href'),a.text) for a in doc.select('a[href]')}
        self.assertTrue(links(before)<=links(after))
        spec=importlib.util.spec_from_file_location('daily',u.ROOT.parents[1]/'update_daily_tables.py')
        daily=importlib.util.module_from_spec(spec); spec.loader.exec_module(daily)
        manifest={'inputs':{},'requested_at':'test','markets':{'AI':{'asOf':'test'}},'weco':{'available_at_request':0},'review_queue':str(u.ROOT/'latest.json')}
        with TemporaryDirectory(dir=u.ROOT) as folder:
            target=Path(folder)/'index.html'
            daily.render_index(manifest,[],target)
            doc=BeautifulSoup(target.read_text(encoding='utf-8'),'html.parser')
            self.assertTrue(any((target.parent/a.get('href','')).resolve()==u.ROOT/'index.html' for a in doc.select('a')))

if __name__=='__main__': unittest.main()
