"""UK centered rolling-quarter observations must use their economic period end."""
import json,sys
from pathlib import Path
import pandas as pd,numpy as np
from period_alignment import align_uk_period_ends,ALIGNMENTS
B=Path(__file__).resolve().parent
raw=pd.read_csv(B/'source/raw_haver.csv')
raw['month']=pd.PeriodIndex(raw.date,freq='M').to_timestamp('M')
data=raw[raw.pk.isin(ALIGNMENTS)].pivot(index='month',columns='pk',values='value').sort_index()
data=data.reindex(pd.date_range(data.index.min(),data.index.max()+pd.offsets.MonthEnd(1),freq='ME'))
before=data.copy()
specs={'UK|'+p:{'note':''} for p in ALIGNMENTS}
aligned,_=align_uk_period_ends(data,specs)
for p in ALIGNMENTS:
 pd.testing.assert_series_equal(aligned[p],before[p].shift(1))
d=json.loads((B/'dashboard_data.json').read_text(encoding='utf8'))
assert d['period_alignment']==ALIGNMENTS
inputs=d['input_series']['UK'];dates=inputs['dates']
for p in ALIGNMENTS:
 expected=before[p].shift(1).reindex(pd.to_datetime(dates).to_period('M').to_timestamp('M'))
 actual=np.array(inputs['series'][p]['raw'],dtype=float)
 np.testing.assert_allclose(actual,expected.to_numpy(),atol=1e-6,equal_nan=True)
# Pinned ONS reference fixture tests the calendar without freezing future revisions.
fixture=pd.DataFrame({'g10:s112ele':[np.nan,34577,np.nan,np.nan], 'uk:ap2y':[np.nan,704,691,np.nan]},index=pd.date_range('2026-06-30',periods=4,freq='ME'))
aligned_fixture,_=align_uk_period_ends(fixture,{'UK|'+p:{'note':''} for p in ALIGNMENTS})
assert aligned_fixture.at[pd.Timestamp('2026-08-31'),'g10:s112ele']==34577
assert aligned_fixture.at[pd.Timestamp('2026-08-31'),'uk:ap2y']==704
assert aligned_fixture.at[pd.Timestamp('2026-09-30'),'uk:ap2y']==691
employment=next(r for r in d['indicators'] if r['country']=='UK' and r['pk']=='g10:s112ele')
if inputs['series']['g10:s112ele']['zscore'][dates.index(employment['date'])] is not None:assert employment['loading'] is not None
# The correction changes only UK's Consumer block and its headline derivatives.
before_path=B.parent/'outputs/uk_consumer_audit/model_before.json'
if '--compare-before' in sys.argv and before_path.exists():
 old=json.loads(before_path.read_text(encoding='utf8'))
 for cc,c in d['countries'].items():
  if cc!='UK':assert c==old['countries'][cc]
  else:
   for ver in ['YoY','Momentum']:
    for axis in ['Capex','Housing','Export']:assert c['versions'][ver]['blocks'][axis]==old['countries'][cc]['versions'][ver]['blocks'][axis]
print('PASS: centered-to-end alignment, source data unchanged, ONS reference periods, employment present in August')
