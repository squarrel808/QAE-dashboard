import json
from pathlib import Path
import tempfile
import unittest
import pymupdf as fitz
import research_context as m


class ResearchTests(unittest.TestCase):
    def test_pdf_bullet_normalization_is_limited(self):
        self.assertEqual(m.evidence_norm('the last hike of this \r\nn\r\ntightening cycle'),
                         'the last hike of this tightening cycle')
        self.assertEqual(m.evidence_norm('variable n is not a bullet'), 'variable n is not a bullet')
        self.assertEqual(m.evidence_norm('2.75%\n2027'), '2.75% 2027')

    def test_country_title_classification(self):
        countries,topics=m.classify('Germany: GDP and inflation outlook')
        self.assertIn('DE',countries); self.assertEqual(countries['EA'],'eurozone_member_in_title')
        self.assertIn('growth',topics); self.assertIn('inflation',topics)
        self.assertNotIn('US',m.classify('Australia: Growth continues')[0])
        self.assertNotIn('EA',m.classify('European markets: UK GDP')[0])

    def test_dates_are_not_download_dates(self):
        self.assertEqual(m.filename_date('2026-08-31_Growth.pdf'),'2026-08-31')
        self.assertEqual(m.filename_date('20260831_Growth.pdf'),'2026-08-31')
        self.assertIsNone(m.filename_date('20260230_Growth.pdf'))
        self.assertIsNone(m.filename_date('Growth.pdf'))

    def test_date_conflicts_flagged(self):
        path=Path.cwd()/'raw/GS/20260901_Inflation.pdf'
        result=m.choose_metadata(path,Path.cwd()/'raw',{m.path_key(path):{'published':'2026-09-02','title':'Inflation','house':'GS'}})
        self.assertEqual(result['date_review'],1)

    def test_disclosure_does_not_enter_chunks(self):
        text='The economy has continued to expand and inflation is easing. '*10+'\nImportant Disclosures\nUNRELATED_DISCLOSURE'
        result=m.chunks(text)
        self.assertTrue(result)
        self.assertNotIn('UNRELATED_DISCLOSURE',' '.join(result))

    def test_ingest_dedup_and_rerun_no_source_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); raw=root/'raw'; (raw/'GS').mkdir(parents=True)
            fixture=fitz.open(); p=fixture.new_page()
            p.insert_text((50,70),'United States inflation and wage growth outlook.\n'*8)
            payload=fixture.tobytes(); fixture.close()
            first=raw/'GS/20260901_US inflation.pdf'; first.write_bytes(payload)
            (raw/'GS/20260901_same_copy.pdf').write_bytes(payload)
            result=m.ingest(raw,root/'data',root/'output')
            self.assertEqual(result['new_documents'],1)
            self.assertEqual(result['duplicate_content'],1)
            self.assertNotIn('failed',result)
            repeat=m.ingest(raw,root/'data',root/'output')
            self.assertEqual(repeat['unchanged'],2)
            self.assertEqual(first.read_bytes(),payload)
            db=m.connect(root/'data')
            try:
                self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],1)
                self.assertTrue(m.search(db,'inflation',country='US'))
                # Filename-only date must not silently enter historical point-in-time comparison.
                self.assertEqual(m.search(db,'inflation',asof='2026-09-09'),[])
                doc_id=db.execute('SELECT doc_id FROM documents').fetchone()[0]
                db.execute('UPDATE documents SET date_review=0'); db.commit()
                self.assertTrue(m.search(db,'inflation',asof='2026-09-09'))
                self.assertEqual(m.search(db,'inflation',asof='2026-08-01'),[])
                self.assertTrue(m.packet(db,root/'packets','US').is_file())
                claim={'claim_id':'c1','doc_id':doc_id,'page':1,'country':'US','topic':'inflation','claim':'검토 초안','evidence_quote':'United States inflation and wage growth outlook.'}
                claims=root/'claims.json'; claims.write_text(json.dumps([claim]),encoding='utf-8')
                self.assertEqual(m.import_claims(db,claims),1)
                self.assertEqual(db.execute('SELECT review_status FROM claims').fetchone()[0],'draft')
                claim['claim_id']='c2'; claim['evidence_quote']='An invented statement that is not actually in this source document.'
                claims.write_text(json.dumps([claim]),encoding='utf-8')
                with self.assertRaises(ValueError): m.import_claims(db,claims)
                self.assertEqual(db.execute('SELECT count(*) FROM claims').fetchone()[0],1)
            finally: db.close()

    def test_bad_pdf_remains_a_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); raw=root/'raw'; raw.mkdir()
            (raw/'bad.pdf').write_bytes(b'<html>login</html>')
            result=m.ingest(raw,root/'data',root/'output')
            self.assertEqual(result['failed'],1)
            self.assertEqual((raw/'bad.pdf').read_bytes(),b'<html>login</html>')


if __name__=='__main__': unittest.main()
