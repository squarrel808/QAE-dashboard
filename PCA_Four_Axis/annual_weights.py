"""Freeze one GDP-weight snapshot per country/calendar year.

Historical release vintages are unavailable. At initial creation use current
revised data with the documented publication-lag eligibility rule; thereafter
never overwrite a saved country-year snapshot during a routine update.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

OLD_POLICY='january_1_ttm_lagged_frozen_v1'
NET_POLICY='january_1_ttm_lagged_frozen_net_exports_v2'
POLICY='january_1_ttm_lagged_frozen_half_exports_v3'

def migrate_export_weights(candidate_shares,country,records,sources):
    """User-authorized definition change; retain year, quarter and other weights."""
    for record in records.values():
        if record['country']!=country or record['policy']==POLICY:continue
        if record['policy'] not in [OLD_POLICY,NET_POLICY]:raise ValueError('Unknown legacy weight policy')
        quarter=pd.Period(record['quarter'],freq='Q')
        gross=record.get('previous_gross_export_weight')
        if record['policy']==OLD_POLICY:gross=record['weights']['Export']
        if gross is None:
            if quarter not in candidate_shares.index:raise ValueError('Missing export source at frozen quarter')
            gross=2*float(candidate_shares.at[quarter,'Export'])
        if not np.isfinite(gross) or gross<0:raise ValueError('Invalid gross export share')
        record['previous_export_weight']=record['weights']['Export']
        record['previous_gross_export_weight']=gross
        record['weights']['Export']=0.5*gross
        record['policy']=POLICY;record['sources']=sorted(set(record['sources'])|set(sources))
        record['export_weight_definition']='0.5 * nominal gross exports / GDP; no redistribution'
        record['migration_kst']=pd.Timestamp.now(tz='Asia/Seoul').isoformat()

def resolve_year(candidate_shares, country, year, lag_months, records, sources, now=None):
    key=f'{country}:{year}'
    if key in records:
        record=records[key]
        if record['policy']!=POLICY:raise ValueError('Annual weight policy mismatch')
        return record
    cutoff=pd.Timestamp(year=year,month=1,day=1)
    now=pd.Timestamp.now(tz='Asia/Seoul') if now is None else pd.Timestamp(now)
    if year>now.year:return None
    eligible=[]
    for quarter,row in candidate_shares.iterrows():
        available=quarter.asfreq('M').to_timestamp('M')+pd.offsets.MonthEnd(lag_months)
        if available<=cutoff and row.notna().all():eligible.append((quarter,available,row))
    if not eligible:return None  # Never backfill an early year with future GDP.
    quarter,available,row=eligible[-1]
    if not np.isfinite(row.to_numpy(dtype=float)).all() or (row.drop(labels='Export')<=0).any() or row['Export']<0:
        raise ValueError(f'{country} {year}: invalid GDP shares')
    record={'policy':POLICY,'country':country,'year':int(year),'cutoff':str(cutoff.date()),
            'quarter':str(quarter),'assumed_available':str(available.date()),
            'publication_lag_months':lag_months,'weights':{k:float(v) for k,v in row.items()},
            'sources':sources,'created_kst':now.isoformat(),
            'vintage_note':'Current revised data at snapshot creation; release eligibility approximated by lag, not a historical real-time vintage.'}
    records[key]=record
    return record

def weight_panel(candidate_shares,country,index,lag_months,records,sources,now=None):
    panel=pd.DataFrame(index=index,columns=candidate_shares.columns,dtype=float)
    quarters=pd.Series(index=index,dtype=object);selected=[]
    for year in sorted(set(index.year)):
        record=resolve_year(candidate_shares,country,int(year),lag_months,records,sources,now)
        if record is None:continue
        mask=index.year==year
        panel.loc[mask,:]=pd.Series(record['weights']).reindex(panel.columns).to_numpy()
        quarters.loc[mask]=record['quarter'];selected.append(record)
    return panel,quarters,selected

def read_ledger(path):
    if not path.exists():return {}
    data=json.loads(path.read_text(encoding='utf8'))
    if data['policy'] not in [POLICY,OLD_POLICY,NET_POLICY]:raise ValueError('Unrecognized GDP-weight snapshot policy')
    return data['records']

def save_ledger(path,records):
    content=json.dumps({'policy':POLICY,'records':records},ensure_ascii=False,indent=2,allow_nan=False)
    if path.exists() and path.read_text(encoding='utf8')==content:return
    temp=path.with_suffix('.tmp');temp.write_text(content,encoding='utf8');temp.replace(path)
