"""Read-only monthly coverage check against the currently selected PCA II/III inputs.

Refreshes Haver observations into an audit folder, never production inputs/models.
No imputation or relaxed publication rule is applied.
"""
import argparse
import hashlib
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'PCA/PCA_Four_Axis'))
from build import core
from period_alignment import ALIGNMENTS

DEPENDENCIES = {'derived:uk_mgsx_endmonth': ['uk:mgsx'],
                'derived:fr_car_light': ['france:frnopcr', 'france:frnolcvr']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--month', required=True)
    parser.add_argument('--cached', action='store_true')
    args = parser.parse_args()
    month = pd.Period(args.month, freq='M')
    target = month.to_timestamp('M')
    out = ROOT / 'outputs' / ('pca_coverage_' + str(month))
    out.mkdir(exist_ok=True)
    folders = {'II': 'PCA/PCA_Four_Axis', 'III': 'PCA/PCA_BlackRock_Only'}
    models = {m: core.READ(ROOT / f / 'dashboard_data.json') for m, f in folders.items()}
    protected = [ROOT / f / name for f in folders.values() for name in
                 ['dashboard_data.json', 'index.html', 'indices.csv', 'annual_weights.json']]
    protected += [ROOT / 'PCA/PCA_Four_Axis' / p for p in
                  ['source/raw_haver.csv', 'values.csv', 'blackrock_source/values.csv']]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    wanted = sorted({pk for d in models.values() for s in d['indicators']
                     for pk in DEPENDENCIES.get(s['pk'], [s['pk']])})
    if not args.cached:
        import Haver
        warnings.filterwarnings('ignore')
        Haver.direct('force')
        groups = defaultdict(list)
        for pk in wanted:
            groups[pk.split(':')[0]].append(pk)
        metadata, values, errors = {}, [], []
        for db, pks in groups.items():
            for i in range(0, len(pks), 20):
                batch = pks[i:i + 20]
                tickers = [p.split(':')[1] + '@' + db for p in batch]
                try:
                    meta = Haver.metadata(tickers)
                    records = json.loads(meta.to_json(orient='records', date_format='iso'))
                    found = {r['database'].lower() + ':' + r['code'].lower(): r for r in records}
                    if set(found) != set(batch):
                        raise ValueError('Missing metadata: ' + str(set(batch) - set(found)))
                    if any(r['frequency'] != 'M' for r in found.values()):
                        raise ValueError('Nonmonthly input frequency')
                    metadata.update(found)
                    data = Haver.data(tickers, startdate=str((month - 36).start_time.date()), dates=True)
                    for pk in batch:
                        cols = [c for c in data if str(c).lower() == pk.split(':')[1]]
                        if len(cols) != 1:
                            raise ValueError('Missing data column: ' + pk)
                        series = pd.to_numeric(data[cols[0]], errors='coerce').dropna()
                        if series.empty:
                            raise ValueError('No observations: ' + pk)
                        values.extend(dict(pk=pk, date=str(t)[:10], value=float(v)) for t, v in series.items())
                except Exception as exc:
                    errors.append(dict(codes=batch, error=str(exc)))
            print('Haver checked', db, len(pks), flush=True)
        log = dict(checked_kst=pd.Timestamp.now(tz='Asia/Seoul').isoformat(),
                   requested=len(wanted), received=len(metadata), observations=len(values), errors=errors)
        (out / 'fetch_log.json').write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf8')
        if errors:
            raise RuntimeError('Haver retrieval incomplete; coverage must not be inferred from failed requests')
        (out / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf8')
        pd.DataFrame(values).to_csv(out / 'observations.csv', index=False, encoding='utf-8-sig')
    metadata = core.READ(out / 'metadata.json')
    log = core.READ(out / 'fetch_log.json')
    assert not log['errors'] and set(metadata) == set(wanted)
    raw = pd.read_csv(out / 'observations.csv')
    raw['month'] = pd.PeriodIndex(raw.date, freq='M').to_timestamp('M')
    wide = raw.pivot(index='month', columns='pk', values='value')
    wide = wide.reindex(pd.date_range(wide.index.min(), max(wide.index.max(), target), freq='ME'))
    wide['derived:uk_mgsx_endmonth'] = wide['uk:mgsx'].shift(1)
    wide['derived:fr_car_light'] = wide['france:frnopcr'] + wide['france:frnolcvr']
    for pk, rule in ALIGNMENTS.items():
        wide[pk] = wide[pk].shift(rule['shift_months'])
    details, categories, countries = [], [], []
    for model, d in models.items():
        for cc, country in d['countries'].items():
            rows = []
            for s in [s for s in d['indicators'] if s['country'] == cc]:
                spec = dict(s)
                dep = DEPENDENCIES.get(s['pk'], [s['pk']])[0]
                spec['seasonal'] = core.classify(metadata[dep], s['previous_group'])[3]
                x = wide[s['pk']]
                y = core.transform(x, spec, 'YoY')
                available = bool(pd.notna(y.at[target]))
                old_input = d['input_series'][cc]
                old_at = old_input['dates'].index(str(month))
                previous_available = old_input['series'][s['pk']]['zscore'][old_at] is not None
                row = dict(model=model, country=cc, axis=s['axis'], pk=s['pk'], label=s['label'],
                           group=s['previous_group'], kind=s['kind'], direction=s['direction'],
                           raw_available=bool(pd.notna(x.at[target])), available=available,
                           previously_available=previous_available,
                           last_raw_month=str(x.last_valid_index())[:7],
                           last_transformed_month=str(y.last_valid_index())[:7],
                           missing_squared_loading=float(s['loading'] ** 2) if not available else 0)
                details.append(row)
                rows.append(row)
            blockers = []
            for axis in d['axes']:
                subset = [s for s in rows if s['axis'] == axis]
                if not subset:
                    continue
                count = sum(s['available'] for s in subset)
                if count < min(2, len(subset)):
                    blockers.append(axis + ': ' + str(count) + '/' + str(len(subset)) + '개 관측')
                categories.append(dict(model=model, country=cc, axis=axis, available=count,
                                       total=len(subset), missing=len(subset)-count,
                                       missing_pct=100*(len(subset)-count)/len(subset),
                                       missing_squared_loading=sum(s['missing_squared_loading'] for s in subset)))
            consumption_actual = sum(s['available'] for s in rows if s['group'] == 'C_actual')
            export_actual = sum(s['available'] for s in rows if s['group'] == 'X' and s['kind'] in ['level', 'growth_yoy', 'growth_mom'])
            if not consumption_actual:
                blockers.append('소비 실적 없음')
            if not export_actual:
                blockers.append('수출 실적 없음')
            n = len(rows)
            missing = sum(not s['available'] for s in rows)
            countries.append(dict(model=model, country=cc, name=d['names'][cc], month=str(month),
                                  current_latest=country['versions']['YoY']['latest'],
                                  total=n, available=n-missing, missing=missing, missing_pct=100*missing/n,
                                  newly_available=sum(s['available'] and not s['previously_available'] for s in rows),
                                  actual_consumption=consumption_actual, actual_export=export_actual,
                                  passes_existing_publication_rules=not blockers, blockers='; '.join(blockers)))
    for p, h in hashes.items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h, p
    result = dict(month=str(month), fetch=log, production_unchanged=True,
                  countries=countries, categories=categories, indicators=details,
                  note='결측은 현재 모델의 변환 후 입력 기준. 기존 로딩 제곱 합계는 지표 중요도 참고이며 GDP 비중이 아님. 게시 가능 여부는 기존 최소 규칙만 확인하며 충분한 자료 품질을 보증하지 않음.')
    (out/'coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    for name, rows in [('countries', countries), ('categories', categories), ('indicators', details)]:
        pd.DataFrame(rows).to_csv(out/(name+'.csv'), index=False, encoding='utf-8-sig')
    print(pd.DataFrame(countries)[['model', 'name', 'available', 'total', 'missing_pct', 'newly_available', 'passes_existing_publication_rules', 'blockers']].to_string(index=False))
    print('Production unchanged; audit saved:', out)


if __name__ == '__main__':
    main()
