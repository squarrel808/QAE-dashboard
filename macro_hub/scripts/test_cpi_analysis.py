"""Validate the published CPI snapshot against raw Haver observations."""
import json
import unittest
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]

class CpiSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'macro_hub/public/data/cpi_analysis.json').read_text(encoding='utf-8'))
        cls.raw=json.loads((ROOT/'haver/haver-api_CPI/cpi_analysis_raw.json').read_text())

    def test_baskets_cover_all_six_countries_without_duplicate_indices(self):
        self.assertEqual(set(self.data['countries']),{'US','Japan','UK','Germany','Australia','Canada','AustraliaQuarterly'})
        for country,v in self.data['countries'].items():
            groups=v['groups']
            self.assertEqual(len(groups),len({g['index'] for g in groups}),country)
            self.assertAlmostEqual(sum(g['observations'][-1]['weight'] for g in groups),100,delta=.06,msg=country)
            for g in groups:
                obs=g['observations']
                self.assertEqual(len({o['date'] for o in obs[-12:]}),12)
                for field in ['mom','yoy','mom_contribution','yoy_contribution']:
                    self.assertIsNotNone(obs[-1][field],(country,g['name'],field))

    def test_calendar_rates_match_raw_prices(self):
        for v in self.data['countries'].values():
            for g in v['groups']:
                frequency='Q' if v.get('frequency')=='Q' else 'M'
                raw={str(pd.Period(k,frequency)):x for k,x in self.raw[g['index']].items()}
                for o in g['observations'][-24:]:
                    d=pd.Period(o['date'],frequency)
                    for key,lag in [('mom',1),('yoy',4 if frequency=='Q' else 12)]:
                        before=raw.get(str(d-lag))
                        if before is None:self.assertIsNone(o[key])
                        else:self.assertAlmostEqual(o[key],(raw[str(d)]/before-1)*100,places=4)

    def test_core_uses_six_complete_months_and_preserves_quarterly_gaps(self):
        for c in self.data['core']:
            raw={k[:7]:v for k,v in self.raw[c['ticker']].items()}
            for o in c['observations'][-12:]:
                d=pd.Period(o['date'],'M')
                six=[raw.get(str(d-i)) for i in range(6)]
                if c['frequency']=='Q' or None in six:self.assertIsNone(o['momentum'])
                else:self.assertAlmostEqual(o['momentum'],((sum(six[:3])/sum(six[3:]))**4-1)*100,places=2)

if __name__=='__main__':unittest.main()
