"""Build country factor coverage and histories from the existing GS connection."""
import datetime as dt
import json
from pathlib import Path
from build_pairbaskets_json import series_daily

HERE = Path(__file__).resolve().parent

def build_major_factors():
    import pandas as pd
    from gs_quant.data import Dataset
    catalog = json.loads((HERE / 'major_factor_catalog.json').read_text(encoding='utf8'))
    series = {}
    for dataset, kinds in [('PAIR_BASKETS_LEVELS', {'pair'}), ('CUSTOM_BASKETS_LEVELS', {'legs', 'basket'})]:
        codes = sorted({code for item in catalog if item['kind'] in kinds for code in item['bbids']})
        ds = Dataset(dataset)
        coverage = ds.get_coverage()
        by_code = {row['bbid']: row for row in coverage.to_dict('records') if row.get('bbid')}
        for offset in range(0, len(codes), 25):
            selected = [code for code in codes[offset:offset + 25] if code in by_code]
            if not selected:
                continue
            id_to_code = {by_code[code]['assetId']: code for code in selected}
            frame = ds.get_data(dt.date(2012, 1, 1), dt.date.today(), assetId=list(id_to_code))
            if frame.empty:
                continue
            if 'date' not in frame.columns:
                frame = frame.reset_index()
            frame['date'] = pd.to_datetime(frame['date'])
            if 'bbid' not in frame.columns:
                frame['bbid'] = frame['assetId'].map(id_to_code)
            for code, group in frame.groupby('bbid'):
                dates, close = series_daily(group)
                if len(dates) >= 2:
                    series[code] = dict(bbid=code, label=by_code[code].get('name') or code, dates=dates, close=close)
        print(dataset, 'factor histories', len(series), flush=True)
    output = dict(checkedAt=dt.datetime.now().astimezone().isoformat(timespec='seconds'), catalog=catalog, series=list(series.values()))
    path = HERE.parent / 'public/data/major_factors.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(output, ensure_ascii=False), encoding='utf8')
    temporary.replace(path)
    print('Saved country factors',len(series),flush=True)

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from gs_quant.session import GsSession, Environment
    load_dotenv(HERE.parents[1] / 'gs_api/.env')
    GsSession.use(Environment.PROD, os.environ['GS_CLIENT_ID'], os.environ['GS_CLIENT_SECRET'], ('read_product_data',))
    build_major_factors()
