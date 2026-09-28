"""Data integrity, chronology, units, and event/state separation tests."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

import living_ib as lib


class LivingIBTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.src=sqlite3.connect(':memory:');self.src.row_factory=sqlite3.Row
        self.src.executescript('''
            CREATE TABLE documents(doc_id TEXT PRIMARY KEY,house TEXT,title TEXT,published TEXT,
                date_review INTEGER,status TEXT,date_basis TEXT,first_ingested TEXT);
            CREATE TABLE pages(doc_id TEXT,page INTEGER,text TEXT);
            CREATE TABLE files(doc_id TEXT,path TEXT);
            CREATE TABLE tags(doc_id TEXT,kind TEXT,value TEXT);
        ''')
        for ident,house,day in [('a','GS','2026-09-01'),('b','GS','2026-09-04'),('c','GS','2026-09-05'),('j','JPM','2026-09-02')]:
            self.src.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',(ident,house,'Test '+ident,day,0,'indexed','test','2026-09-09'))
            self.src.execute('INSERT INTO pages VALUES(?,?,?)',(ident,1,'We expect core CPI to rise by 0.2% m/m.\n n \nPolicy remains conditional.'))
            self.src.execute('INSERT INTO files VALUES(?,?)',(ident,str(self.root/(ident+'.pdf'))))
        self.src.commit()
        self.state=lib.state_db(self.root/'state.sqlite3')

    def tearDown(self):
        self.state.close();self.src.close();self.tmp.cleanup()

    def view(self,ident='v1',doc='a',day='2026-09-01',**kwargs):
        v={'view_id':ident,'house':'GS','country':'US','track':'policy.near_term',
           'effective_date':day,'summary':'물가에 조건부인 정책 판단.','scope':'country_research',
           'assumptions':[],'watch':['US_CORE_CPI'],'analyst_questions':[],'limitations':[],
           'evidence':[{'doc_id':doc,'page':1,'quote':'We expect core CPI to rise by 0.2% m/m.'}],
           'prior_view_id':None,'change':'uncompared','change_note':'직접 비교 미완료.',
           'review_status':'draft','origin':'assistant_review_of_local_reports'}
        return {**v,**kwargs}

    def import_(self,*views):
        return lib.import_views({'schema_version':1,'as_of':'2026-09-09','views':list(views)},self.src,self.state)

    def forecast(self,ident='f1',doc='a',day='2026-09-01',**kwargs):
        f={'forecast_id':ident,'house':'GS','country':'US','indicator':'US_CORE_CPI',
           'reference_period':'2026-08','as_of':day,'unit':'pct_mom','value':0.2,
           'scenario':'base','qualifier':'약 0.2%',
           'evidence':[{'doc_id':doc,'page':1,'quote':'We expect core CPI to rise by 0.2% m/m.'}],
           'prior_forecast_id':None,'change':'uncompared','review_status':'draft',
           'origin':'assistant_review_of_local_reports'}
        return {**f,**kwargs}

    def import_forecasts(self,*forecasts):
        return lib.import_forecasts({'schema_version':1,'as_of':'2026-09-09','forecasts':list(forecasts)},self.src,self.state)

    def event(self,**kwargs):
        e={'schema_version':1,'event_id':'test_only','country':'US','indicator':'US_CORE_CPI',
           'released_at':'2026-09-04T08:30:00-04:00','reference_period':'test_period',
           'unit':'pct_mom','actual':0.3,'consensus':0.2,'previous':0.2,'revised_previous':0.1,
           'source_url':'https://example.com/test-fixture','source_label':'Synthetic test only','is_example':True}
        return {**e,**kwargs}

    def test_idempotent_import_and_immutable_payload(self):
        v=self.view()
        self.assertEqual(self.import_(v)['added'],1)
        self.assertEqual(self.import_(v)['unchanged'],1)
        with self.assertRaises(ValueError):self.import_({**v,'summary':'Overwrite attempt'})
        self.assertEqual(lib.all_views(self.state),[v])

    def test_bad_quote_rolls_back_whole_batch(self):
        bad=self.view('bad')
        bad['evidence'][0]['quote']='We expect core CPI to rise by 0.9% m/m.'
        with self.assertRaises(ValueError):self.import_(self.view(),bad)
        self.assertEqual(lib.all_views(self.state),[])

    def test_cross_house_and_unknown_date_rejected(self):
        with self.assertRaises(ValueError):self.import_(self.view(doc='j',day='2026-09-02'))
        self.src.execute("UPDATE documents SET date_review=1 WHERE doc_id='a'")
        with self.assertRaises(ValueError):self.import_(self.view())

    def test_future_source_and_invalid_page_rejected(self):
        with self.assertRaises(ValueError):self.import_(self.view(doc='c'))
        v=self.view();v['evidence'][0]['page']=2
        with self.assertRaises(ValueError):self.import_(v)

    def test_prior_requires_same_house_country_track_and_time(self):
        self.import_(self.view())
        for field,value in [('country','EA'),('track','inflation.preview')]:
            v=self.view('v2','b','2026-09-04',prior_view_id='v1',change='revised',**{field:value})
            with self.assertRaises(ValueError):self.import_(v)
        with self.assertRaises(ValueError):self.import_(self.view('v3',change='revised'))
        with self.assertRaises(ValueError):self.import_(self.view('v4',prior_view_id='missing',change='maintained'))

    def test_cycle_and_duplicate_ids_rejected(self):
        a=self.view('v1',prior_view_id='v2',change='revised')
        b=self.view('v2',prior_view_id='v1',change='revised')
        with self.assertRaises(ValueError):self.import_(a,b)
        with self.assertRaises(ValueError):self.import_(self.view(),self.view())

    def test_asof_and_same_day_conflicts(self):
        a=self.view()
        b=self.view('v2','b','2026-09-04',prior_view_id='v1',change='revised')
        self.import_(a,b)
        old=lib.current_views(lib.all_views(self.state),'2026-09-03')[0]
        self.assertEqual(old['views'][0]['view_id'],'v1')
        conflict=self.view('v3','b','2026-09-04',summary='Another same-day interpretation')
        self.import_(conflict)
        latest=lib.current_views(lib.all_views(self.state),'2026-09-04')[0]
        self.assertTrue(latest['conflict']);self.assertEqual(len(latest['views']),2)
        self.assertEqual(lib.current_views(lib.all_views(self.state),'2026-08-31'),[])

    def test_event_no_same_day_or_future_leak_and_no_view_mutation(self):
        self.import_(self.view(),self.view('v2','b','2026-09-04',prior_view_id='v1',change='revised'),self.view('v3','c','2026-09-05',prior_view_id='v2',change='maintained'))
        before=lib.canonical(lib.all_views(self.state))
        result=lib.prepare_event(self.event(),self.src,self.state,self.root/'out')
        packet=lib.read_json(Path(result['output'])/'context.json')
        ids=[v['view_id'] for g in packet['house_context'] for v in g['views']]
        self.assertEqual(ids,['v1'])
        self.assertEqual(set(packet['same_day_or_later_excluded']),{'v2','v3'})
        self.assertEqual(packet['surprise_in_input_unit'],0.1)
        self.assertEqual(packet['previous_revision_in_input_unit'],-0.1)
        self.assertEqual(before,lib.canonical(lib.all_views(self.state)))
        lib.prepare_event(self.event(),self.src,self.state,self.root/'out')
        with self.assertRaises(ValueError):lib.prepare_event(self.event(actual=0.8),self.src,self.state,self.root/'out')

    def test_units_missing_actual_timezone_and_unsafe_ids(self):
        for patch in ({'actual':None},{'actual':True},{'actual':float('nan')},{'unit':'index'},
                      {'released_at':'2026-09-04T08:30:00'},{'event_id':'../escape'},
                      {'country':'EA'},{'consensus':'0.2%'},{'source_url':''}):
            with self.subTest(patch=patch),self.assertRaises((ValueError,TypeError)):
                lib.validate_event(self.event(**patch))

    def test_conflicting_event_sibling_is_not_hidden(self):
        self.import_(self.view(),self.view('sibling',watch=['US_PAYROLLS']))
        result=lib.prepare_event(self.event(),self.src,self.state,self.root/'out')
        group=lib.read_json(Path(result['output'])/'context.json')['house_context'][0]
        self.assertTrue(group['conflict']);self.assertEqual(len(group['views']),2)

    def test_unknown_indicator_rejected_without_event_write(self):
        self.import_(self.view())
        with self.assertRaises(ValueError):lib.prepare_event(self.event(indicator='US_UNKNOWN'),self.src,self.state,self.root/'out')
        self.assertEqual(self.state.execute('SELECT count(*) FROM events').fetchone()[0],0)

    def test_rebuild_preserves_all_history_and_outputs_are_deterministic(self):
        self.import_(self.view(),self.view('v2','b','2026-09-04',prior_view_id='v1',change='revised'))
        out=self.root/'out'
        lib.build_outputs(self.src,self.state,out,'2026-09-09')
        first={p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
        lib.build_outputs(self.src,self.state,out,'2026-09-09')
        second={p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.assertEqual(first,second)
        self.assertEqual(len(lib.all_views(self.state)),2)
        self.assertEqual(len(lib.read_json(out/'GS/history.json')),2)
        self.assertIn('이 국가의 견해 근거를 아직 검토하지 않았습니다.',(out/'Citi/MODULE.md').read_text(encoding='utf-8'))

    def test_easing_path_is_shown_in_comparison(self):
        v=self.view(country='CA',track='policy.easing_start',summary='2027년 인하를 예상한다.')
        self.import_(v)
        out=self.root/'out'
        lib.build_outputs(self.src,self.state,out,'2026-09-09')
        comparison=(out/'IB_COMPARE.md').read_text(encoding='utf-8')
        self.assertIn('2027년 인하를 예상한다.',comparison)

    def test_forecast_import_is_immutable_and_source_grounded(self):
        f=self.forecast()
        self.assertEqual(self.import_forecasts(f)['added'],1)
        self.assertEqual(self.import_forecasts(f)['unchanged'],1)
        with self.assertRaises(ValueError):self.import_forecasts({**f,'value':0.3})
        bad=self.forecast('bad');bad['evidence'][0]['quote']='Not in source'
        with self.assertRaises(ValueError):self.import_forecasts(bad)

    def test_forecast_history_scope_and_outputs(self):
        a=self.forecast()
        b=self.forecast('f2','b','2026-09-04',value=0.3,prior_forecast_id='f1',change='revised')
        self.import_forecasts(a,b)
        current=lib.current_forecasts(lib.all_forecasts(self.state),'2026-09-09')[0]
        self.assertEqual(current['forecasts'][0]['forecast_id'],'f2')
        bad=self.forecast('bad','b','2026-09-04',unit='pct_yoy',prior_forecast_id='f1',change='revised')
        with self.assertRaises(ValueError):self.import_forecasts(bad)
        out=self.root/'out';lib.build_outputs(self.src,self.state,out,'2026-09-09')
        self.assertEqual(lib.read_json(out/'summary.json')['current_forecasts'],1)
        self.assertTrue((out/'FORECASTS.md').is_file())
        self.assertEqual(len(lib.read_json(out/'GS/forecasts.json')),1)

    def test_event_includes_only_prior_matching_forecast(self):
        self.import_(self.view())
        self.import_forecasts(self.forecast(),self.forecast('f2','b','2026-09-04',value=0.3,prior_forecast_id='f1',change='revised'))
        result=lib.prepare_event(self.event(),self.src,self.state,self.root/'out')
        packet=lib.read_json(Path(result['output'])/'context.json')
        self.assertEqual(packet['matching_prior_forecasts'][0]['forecasts'][0]['forecast_id'],'f1')


class InitialCorpusTests(unittest.TestCase):
    def test_curated_views_against_real_pages(self):
        root=Path(__file__).resolve().parent
        source=root/'source_snapshot.sqlite3'
        if not source.exists():source=root/'data/research.sqlite3'
        seed=root/'initial_views_20260909.json'
        if not source.exists() or not seed.exists():self.skipTest('Initial corpus is not present')
        src=lib.source_db(source)
        try:
            items=lib.read_json(seed)['views']
            lib.validate_views(items,src)
            self.assertEqual({v['house'] for v in items},set(lib.HOUSES))
            for h in lib.HOUSES:
                self.assertTrue(set(lib.COUNTRIES)-{'GLOBAL'} <= {v['country'] for v in items if v['house']==h})
            groups=lib.current_views(items,'2026-09-09')
            self.assertFalse(any(g['conflict'] for g in groups))
            self.assertTrue(any(v['change']=='revised' and v['house']=='JPM' and v['country']=='EA' for v in items))
            self.assertTrue(any(v['change']=='maintained' and v['house']=='BofA' and v['country']=='CA' for v in items))
        finally:src.close()

    def test_curated_forecasts_against_real_pages(self):
        root=Path(__file__).resolve().parent;source=root/'source_snapshot.sqlite3';seed=root/'initial_forecasts_20260910.json'
        if not source.exists():source=root/'data/research.sqlite3'
        if not source.exists() or not seed.exists():self.skipTest('Initial corpus is not present')
        src=lib.source_db(source)
        try:
            items=lib.read_json(seed)['forecasts'];lib.validate_forecasts(items,src)
            self.assertEqual({f['house'] for f in items},set(lib.HOUSES))
            self.assertTrue(all(f['country']=='US' for f in items))
        finally:src.close()


if __name__=='__main__':unittest.main()
