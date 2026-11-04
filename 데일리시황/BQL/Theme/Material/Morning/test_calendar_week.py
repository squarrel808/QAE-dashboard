from datetime import date
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if p.name=='BQL')))
from period_policy import active_price_sessions,rolling_window
class RollingTests(unittest.TestCase):
    def test_holidays_and_carried_current_date(self):
        dates=[date(2026,9,d) for d in [15,16,17,18,19,20,21,22,23,24,25,26,27,28]]
        # Japan closes Sep 21-23; Sep 28 feed still carries Sep 25 close.
        values=np.array([[100,101,102,103,103,103,103,103,103,104,105,105,105,105]],dtype=float)
        start,end,window=rolling_window(dates,active_price_sessions(values))
        self.assertEqual((dates[start],dates[end]),(date(2026,9,15),date(2026,9,25)))
        self.assertEqual(len(window),6)
    def test_midweek_and_cutoff(self):
        dates=[date(2026,10,d) for d in [20,21,22,23,26,27,28]]
        sessions=active_price_sessions(np.arange(100,107,dtype=float).reshape(1,-1))
        start,end,window=rolling_window(dates,sessions,date(2026,10,27))
        self.assertEqual((dates[start],dates[end]),(date(2026,10,20),date(2026,10,27)))
    def test_incomplete_fails(self):
        with self.assertRaises(ValueError):rolling_window([date(2026,1,1)],[0])
if __name__=='__main__':unittest.main(verbosity=2)
