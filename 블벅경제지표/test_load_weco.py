import sys,unittest,importlib.util
from pathlib import Path
from unittest.mock import patch
import pandas as pd
Q=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Q));sys.path.insert(0,str(Q/'블벅경제지표'))
import load_weco as mod
def frame(name,survey,actual=None):
    return pd.DataFrame([{'Date Time':pd.Timestamp('2026-10-23 10:00'),'Country Code':'US','Event':name,'Period':'Sep','Survey':survey,'Actual':actual,'Prior':None,'Revised':None,'Relevance':90 if survey is not None else 0}])
class ClassificationTest(unittest.TestCase):
    def load(self,*frames):
        with patch.object(mod,'pick_files',return_value=['new','old']),patch.object(mod,'_read',side_effect=frames):
            return mod.load_rows(verbose=False)
    def test_two_indicator_exports_stay_indicators_and_latest_wins(self):
        rows=self.load(frame('CPI',2.1,2.2),frame('CPI',2.0,2.0))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['kind'],'ind')
        self.assertEqual(rows[0]['act'],mod.fmt(2.2))
    def test_indicator_and_speech_keep_independent_types(self):
        rows=self.load(frame('CPI',2.1,2.2),frame('Fed Speech',None))
        self.assertEqual({r['ev']:r['kind'] for r in rows},{'CPI':'ind','Fed Speech':'evt'})
    def test_two_event_exports_are_not_forced_into_indicators(self):
        rows=self.load(frame('Fed Speech',None),frame('BOE Speech',None))
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['kind']=='evt' for r in rows))
if __name__=='__main__':unittest.main()
