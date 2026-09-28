import json,unittest
from pathlib import Path
from build_dashboard import load_calendar,reference,classify,numeric,factual,identity,DEFAULT_RAW,select_views,indicator_search_spec

class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=next(DEFAULT_RAW.glob('ecocal*.xlsx'));cls.events=load_calendar(cls.book)
        cls.payload=json.loads((Path(__file__).parent/'dist/dashboard_data.json').read_text(encoding='utf-8'))
    def row(self,n):return next(e for e in self.events if e['source_row']==n)
    def test_every_input_field_and_row_preserved(self):
        self.assertEqual(len(self.events),136)
        self.assertEqual(len({e['id'] for e in self.events}),136)
        self.assertTrue(all(set(e['raw'])==set('BCDEFGHIJK') for e in self.events))
        self.assertEqual(sum(e['actual'] is not None for e in self.events),51)
    def test_missing_is_not_zero(self):
        self.assertIsNone(numeric('#N/A'));self.assertEqual(numeric(0),0)
        self.assertIsNone(self.row(80)['actual']);self.assertIsNone(self.row(80)['surprise'])
        self.assertIn('미수록',factual(self.row(80)))
    def test_revision_uses_revised_prior(self):
        e=self.row(32);self.assertEqual(e['actual'],162);self.assertEqual(e['baseline'],21)
        self.assertEqual(e['revision'],44);self.assertEqual(e['actual_change'],141);self.assertEqual(e['surprise'],107)
    def test_annualized_and_nonannualized_are_separate(self):
        self.assertEqual(self.row(39)['unit'],'pct_qoq_annualized');self.assertEqual(self.row(40)['unit'],'pct_qoq')
        self.assertEqual(self.row(39)['actual'],1.4);self.assertEqual(self.row(40)['actual'],0.4)
    def test_month_and_target_period_are_separate(self):
        self.assertEqual(self.row(39)['release_month'],'2026-09');self.assertEqual(self.row(39)['reference_month'],'2026-Q2')
        self.assertEqual(reference('Dec F','2027-01-15'),'2026-12');self.assertEqual(reference('4Q F','2027-02-15'),'2026-Q4')
    def test_classification_and_liquidity_exception(self):
        self.assertEqual(self.row(41)['theme'],'inflation');self.assertEqual(self.row(38)['family'],'wages')
        self.assertEqual(self.row(125)['family'],'policy_rate');self.assertEqual(self.row(127)['family'],'liquidity')
        self.assertTrue(self.row(127)['classification_note'])
    def test_row_reorder_cannot_move_direct_comment(self):
        n=json.loads((Path(__file__).parent/'reviewed_comments.json').read_text(encoding='utf-8'))['comments'][0]
        e=self.row(26);self.assertEqual(identity(n['match']),identity(e))
        copy=dict(e);copy['source_row']=900;self.assertEqual(identity(copy),identity(e))
        copy['period']='Aug';self.assertNotEqual(identity(copy),identity(e))
    def test_no_unrelated_cpi_view_on_trade(self):
        fake={'view_id':'x','house':'GS','country':'US','effective_date':'2026-09-01','track':'inflation.preview','prior_view_id':None,'watch':['US_CORE_CPI']}
        selected,_=select_views([fake],self.row(19),'GS','2026-09-11');self.assertEqual(selected,[])
    def test_pmi_search_is_indicator_and_subtype_specific(self):
        e=next(e for e in self.events if e['family']=='pmi' and 'Composite' in e['event'])
        spec=indicator_search_spec(e)
        self.assertIn('"PMI"',spec['query'])
        self.assertIn('"purchasing managers"',spec['query'])
        self.assertIn('"composite"',spec['query'])
    def test_search_candidates_are_not_mislabeled_as_comments(self):
        candidates=0
        for e in self.payload['events']:
            for h in e['houses']:
                items=h.get('search_candidates',[]);candidates+=len(items)
                if h['status']=='candidate':self.assertTrue(items)
                for item in items:
                    self.assertEqual(item['house'],h['house'])
                    self.assertIn(item['match_scope'],{'country','region','country_text','region_text'})
                    self.assertIn(item['timing'],{'after_release_candidate','same_day_timing_unverified','pre_release_candidate'})
                    self.assertTrue(item['search_query'] and item['excerpt'] and Path(item['path']).is_file())
        self.assertGreater(candidates,0)
    def test_forecast_match_never_mixes_core_headline_or_units(self):
        for e in self.payload['events']:
            for h in e['houses']:
                for f in h['forecasts']:
                    self.assertEqual((f['country'],f['indicator'],f['unit'],f['reference_period']),(e['country_code'],e['indicator'],e['unit'],e['reference_month']))
                    self.assertLess(f['as_of'],e['date'])
    def test_evidence_labels_and_house_counts(self):
        for e in self.payload['events']:
            self.assertEqual(len(e['houses']),5)
            for h in e['houses']:
                if h['status']=='reaction':self.assertTrue(any(d['kind']=='reaction' for d in h['direct']))
                if h['status']=='inferred':self.assertTrue(h['bases'])
                for item in h['direct']+h['bases']+h['forecasts']:
                    self.assertTrue(all(r['house']==h['house'] and r['quote'] and Path(r['path']).is_file() for r in item['evidence']))

if __name__=='__main__':unittest.main()
