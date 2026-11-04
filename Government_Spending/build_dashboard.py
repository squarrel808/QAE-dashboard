"""Build a standalone fiscal dashboard from the saved Haver snapshot."""
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
NAMES = {'us':'미국','uk':'영국','fr':'프랑스','de':'독일','ca':'캐나다','jp':'일본','au':'호주'}

def main():
    raw = pd.read_csv(BASE/'values.csv', parse_dates=['date'])
    assert not raw.duplicated(['pk','date']).any()
    wide = raw.pivot(index='date', columns='pk', values='value')
    rows = []
    for country in list(NAMES)[:-1]:
        frame = wide[[f'canada:fg{k}{country}' for k in ['e','r','b']]].dropna()
        frame.columns = ['expenditure','revenue','balance']
        assert (frame.revenue-frame.expenditure-frame.balance).abs().max() < .151
        for date, row in frame.iterrows():
            rows.append(dict(country=country, year=date.year, **row.to_dict()))
    au = wide.filter(like='anz:').dropna(how='all')
    au.index = au.index.to_period('Q')
    au = au.reindex(pd.period_range(au.index.min(),au.index.max(),freq='Q'))
    # Derive expenditure consistently with the published net lending/borrowing.
    amounts = pd.DataFrame({'revenue':au['anz:aunfur'], 'balance':au['anz:aunfu'], 'gdp':au['anz:aunngdp']})
    amounts['expenditure'] = amounts.revenue-amounts.balance
    annual = amounts.groupby(amounts.index.year).sum(min_count=4).dropna()
    for year, row in annual.iterrows():
        rows.append(dict(country='au', year=int(year), **{k:100*row[k]/row.gdp for k in ['expenditure','revenue','balance']}))
    trailing = amounts.rolling(4,min_periods=4).sum().dropna()
    ttm = pd.DataFrame({k:100*trailing[k]/trailing.gdp for k in ['expenditure','revenue','balance']})
    ttm.index.name = 'quarter'
    ttm.to_csv(BASE/'australia_trailing_four_quarters.csv',encoding='utf-8-sig')
    audit = pd.DataFrame({'published_balance':au['anz:aunfu'], 'revenue_less_expenses_less_net_acquisition':au['anz:aunfur']-au['anz:aunfue']-au['anz:aunfun']})
    audit['difference_million_aud'] = audit.iloc[:,1]-audit.iloc[:,0]
    audit.to_csv(BASE/'australia_identity_audit.csv',encoding='utf-8-sig')
    result = pd.DataFrame(rows).sort_values(['country','year'])
    assert result.country.nunique() == 7
    assert not result.duplicated(['country','year']).any()
    assert result[['expenditure','revenue','balance']].notna().all().all()
    result.to_csv(BASE/'annual_fiscal_gdp.csv',index=False,encoding='utf-8-sig')
    common = sorted(set.intersection(*[set(result.loc[result.country==c,'year']) for c in NAMES]))
    assert common
    meta = json.loads((BASE/'metadata.json').read_text(encoding='utf8'))
    log = json.loads((BASE/'fetch_log.json').read_text(encoding='utf8'))
    payload = dict(names=NAMES, rows=result.to_dict('records'), common=common,
                   fetched=log['checked_kst'], metadata=meta,
                   au_ttm=[dict(quarter=str(q),**r.to_dict()) for q,r in ttm.iterrows()])
    (BASE/'dashboard_data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    template = (BASE/'template.html').read_text(encoding='utf8')
    (BASE/'index.html').write_text(template.replace('__DATA__',json.dumps(payload,ensure_ascii=False,allow_nan=False)),encoding='utf8')
    print('7 countries; common latest year:',common[-1],'; AU TTM:',ttm.index[-1])
    print(result[result.year==common[-1]].round(2).to_string(index=False))

if __name__=='__main__':
    main()
