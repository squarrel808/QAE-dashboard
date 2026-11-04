"""Official market BM from the user-supplied BQuant Index Level sheet."""
from contextlib import closing
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
import hashlib
import math
import os

RAW = Path(r'C:\Users\infomax\Documents\python\QAE\____Rawdata___')
CODES = {'STOXX600':'SXXP Index','SP500':'SPX Index','TOPIX':'TPX Index','HANGSENG':'HSI Index','DAX':'DAX Index','UKX':'UKX Index','ASX200':'AS51 Index','CSI300':'SHSZ300 Index'}

def latest_source():
    explicit = os.environ.get('QAE_INDEX_LEVEL_SOURCE')
    if explicit:
        return Path(explicit)
    files = [p for p in RAW.iterdir() if p.name.lower().startswith('bquant_') and p.suffix.lower() in ('.xlsb','.xlsx') and not p.name.startswith('~$')]
    return max(files, key=lambda p:p.stat().st_mtime_ns)

def _date(value):
    if isinstance(value, datetime): return value.date().isoformat()
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, (int,float)) and 20000 < value < 80000:
        return (datetime(1899,12,30)+timedelta(days=value)).date().isoformat()

@lru_cache(maxsize=4)
def _read(path, modified, size):
    source = Path(path)
    if source.suffix.lower() == '.xlsb':
        from pyxlsb import open_workbook
        with open_workbook(source) as book:
            with book.get_sheet('Index Level') as sheet:
                rows = [[c.v for c in row] for row in sheet.rows()]
    else:
        import openpyxl
        with closing(openpyxl.load_workbook(source,read_only=True,data_only=True)) as book:
            rows = list(book['Index Level'].iter_rows(values_only=True))
    headers = [i for i,row in enumerate(rows) if len(row)>3 and row[1] in ('',None) and _date(row[2]) and _date(row[3])]
    # The supplied sheet repeats the maintained 10-metric order. Price is
    # block 5 (after P/E, blended EPS, FY1 EPS and FY2 EPS), not block 1.
    if len(headers) != 10: raise ValueError('Index Level: expected 10 dated metric blocks')
    anchor = headers[4]
    dates = {j:_date(v) for j,v in enumerate(rows[anchor]) if j>=2 and _date(v)}
    levels = {}
    for row in rows[anchor+1:headers[5]]:
        if len(row)>1 and isinstance(row[1],str) and row[1].endswith(' Index'):
            levels[row[1]] = {d:float(row[j]) for j,d in dates.items() if j<len(row) and isinstance(row[j],(int,float)) and math.isfinite(row[j]) and row[j]>0}
    with source.open('rb') as stream: digest = hashlib.file_digest(stream,'sha256').hexdigest()
    return levels, {'source':str(source),'sourceSHA256':digest,'sheet':'Index Level','field':'Price','priceHeaderRow':anchor+1,'method':'end level / start level - 1'}

def series(code, dates):
    source = latest_source(); stat = source.stat()
    levels, meta = _read(str(source),stat.st_mtime_ns,stat.st_size)
    if code not in levels: raise ValueError(f'Index Level Price missing: {code}')
    values = levels[code]
    missing = [d for d in dates if str(d) not in values]
    if missing: raise ValueError(f'Index Level {code}: missing requested dates {missing[:3]}')
    return [[str(d),values[str(d)]] for d in dates], {**meta,'code':code}

def apply_market(market):
    code = CODES[market['key']]
    dates = [market['asOf']] + [d for d in market['periodStart'].values() if d]
    values, meta = series(code, dates)
    lookup = dict(values); end = lookup[market['asOf']]
    benchmark = market['benchmark']
    benchmark.setdefault('constituentReturns',dict(benchmark['returns']))
    benchmark['returns'] = {p:end/lookup[d]-1 if d else None for p,d in market['periodStart'].items()}
    benchmark['indexLevel'] = {**meta,'endDate':market['asOf'],'endLevel':end,'periods':{p:{'startDate':d,'startLevel':lookup[d] if d else None,'endDate':market['asOf'],'endLevel':end} for p,d in market['periodStart'].items()}}
    return market

def apply_ai(data):
    values, meta = series('SPX Index', data['dates'])
    lookup = dict(values); end = lookup[data['meta']['asOf']]
    data['benchmark'].setdefault('constituentReturns',dict(data['benchmark']['returns']))
    data['benchmark']['series'] = values
    data['benchmark']['returns'] = {p:round(end/lookup[d]-1,6) if d else None for p,d in data['periodStarts'].items()}
    data['benchmark']['indexLevel'] = {**meta,'endDate':data['meta']['asOf'],'endLevel':end}
    for mode in data['modes'].values():
        for stage in mode.values():
            for period, perf in stage['performance'].items():
                bm = data['benchmark']['returns'].get(period)
                perf['relative'] = round(perf['return']-bm,6) if perf['return'] is not None and bm is not None else None
    data['notes'] = [n.replace('비교지수는 현재 S&P 500 Raw 패널 전체 종목의 주식수 가중 집계가격이다.','비교지수는 BQuant Index Level 시트의 S&P 500 Price 레벨 수익률이다.') for n in data.get('notes',[])]
    return data
