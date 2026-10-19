import unittest
from build_earnings_calendar import parse_events

HEADER = 'CompanyTickerMarket Cap (USD)Expected Report Date'

class EarningsTests(unittest.TestCase):
    def test_concatenated_company_boundaries(self):
        rows = parse_events(HEADER+'IBMIBM218,707,077,2952026-10-21Eaton Corp PLCETN151,961,500,0002026-11-04Berkshire Hathaway IncBRK/B1,138,885,966,3552026-11-023M CoMMM83,367,310,9982026-10-22')
        self.assertEqual({r['ticker']:r['name'] for r in rows}, {'IBM':'IBM','ETN':'Eaton Corp PLC','BRK/B':'Berkshire Hathaway Inc','MMM':'3M Co'})
        self.assertTrue(all(r['time']=='시간 미제공' for r in rows))

    def test_rejects_bad_or_partial_input(self):
        for body in ['Apple IncAAPL5,012,517,062,8002026-02-30', 'Apple IncAAPL5,012,517,062,8002026-11-02garbage', '']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_events(HEADER+body)

    def test_duplicate_ticker_fails(self):
        with self.assertRaises(ValueError):
            parse_events(HEADER+'Apple IncAAPL5,012,517,062,8002026-11-02Apple IncAAPL5,012,517,062,8002026-11-03')

if __name__=='__main__': unittest.main()
