"""Use supplied Index Level observations for index-level dashboard measures."""
from datetime import date, timedelta
from pathlib import Path
import hashlib
import numpy as np


def load(builder, source=None):
    if source is None:
        folder = builder.BQL_DIR.parents[1] / '____Rawdata___'
        candidates = [p for p in folder.glob('*') if p.name.lower().startswith('bquant_')
                      and p.suffix.lower() in ('.xlsb', '.xlsx') and not p.name.startswith('~$')]
        source = max(candidates, key=lambda p: p.stat().st_mtime_ns)
    source = Path(source)
    if source.suffix.lower() == '.xlsb':
        rows = builder.rows_from_xlsb(source, 'Index Level')
    else:
        book = builder.openpyxl.load_workbook(source, read_only=True, data_only=True)
        try:
            rows = list(book['Index Level'].iter_rows(values_only=True))
        finally:
            book.close()
    headers = [i for i, row in enumerate(rows) if len(row) > 3 and row[1] in ('', None)
               and builder.excel_date(row[2]) and builder.excel_date(row[3])]
    keys = list(builder.METRIC_PREFIXES.values())
    if len(headers) != len(keys):
        raise ValueError('Index Level must contain the maintained 10 metric blocks')
    output = {}
    for block, (start, key) in enumerate(zip(headers, keys)):
        end = headers[block + 1] if block + 1 < len(headers) else len(rows)
        columns = [(j, builder.excel_date(v)) for j, v in enumerate(rows[start]) if j >= 2 and builder.excel_date(v)]
        for row in rows[start + 1:end]:
            if len(row) < 2 or not isinstance(row[1], str) or not row[1].endswith(' Index'):
                continue
            code = row[1].split()[0]
            output.setdefault(code, {})[key] = {d: builder.numeric(row[j]) for j, d in columns if j < len(row)}
    return output, {'source': str(source.resolve()), 'sheet': 'Index Level',
                    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'method': 'Direct index observations; end / start - 1. TPX500 constituents use TPX Index benchmark.'}


def apply(builder, raw, rows, boxes, histories, official, config):
    code = 'TPX' if raw.code == 'TPX500' else raw.code
    if code not in official:
        raise ValueError(f'Index Level missing {code}; constituent aggregation is not an index fallback')
    metrics = official[code]
    # Index history has its own start date; a recently added constituent panel
    # must not reset the index's advertised January baseline.
    dates = sorted(d for d in metrics['price'] if d <= raw.dates[-1])
    if not dates or dates[-1] != raw.dates[-1]:
        raise ValueError(f'Index Level {code} is stale relative to Master')
    def value(key, day):
        return metrics[key].get(day, np.nan)
    def change(key, end, start):
        a, z = value(key, start), value(key, end)
        return z / a - 1 if np.isfinite(a) and a > 0 and np.isfinite(z) and z > 0 else np.nan
    def back(day):
        return dates[builder.nearest_date_index(dates, day)] if day >= dates[0] else None
    current = dates[-1]
    row = next(r for r in rows if r['level'] == 'Index')
    # Constituent calculations are retained only for breadth/coverage and group
    # contribution denominators. Never expose them as index financial measures.
    for field in builder.ROW_FIELDS:
        if field.startswith(('eps', 'price', 'pe', 'roe', 'opm')) and 'Coverage' not in field and 'Weight' not in field:
            row[field] = np.nan
    row['fy2Growth'] = row['momentum'] = row['mcap'] = np.nan
    for suffix, days in [('4', 28), ('13', 91), ('6m', 182)]:
        row['eps' + suffix] = change('eps12', current, back(current - timedelta(days=days)))
    for suffix, days in [('1m', 28), ('3m', 91), ('6m', 182)]:
        row['price' + suffix] = change('price', current, back(current - timedelta(days=days)))
    prices = np.array([[value('price', d) for d in dates]])
    sessions = builder.active_market_session_indices(dates, prices)
    for suffix, offset in [('1d', 1), ('5d', 5)]:
        end = dates[sessions[-1]]
        start = dates[sessions[-1-offset]] if len(sessions) > offset else None
        row['price' + suffix] = change('price', end, start)
        row['eps' + suffix] = change('eps12', end, start)
    row['momentum'] = row['eps4'] - row['eps13'] * 4 / 13
    for field, key in [('peCurrent', 'pe'), ('roeCurrent', 'roe_current'), ('roe12m', 'roe_12m'),
                       ('opmCurrent', 'opm_current'), ('opm12m', 'opm_12m'), ('mcap', 'mcap')]:
        row[field] = value(key, current)
    fy1, fy2 = value('eps_fy1', current), value('eps_fy2', current)
    row['fy2Growth'] = fy2 / fy1 - 1 if fy1 > 0 and np.isfinite(fy2) else np.nan
    pe = np.array([value('pe', d) for d in dates])
    stats = builder.pe_box_stats(pe)
    row['pePercentile'] = stats['percentile']
    box = next(b for b in boxes if b['level'] == 'Index')
    box.update(stats)
    history = next(h for h in histories if h['level'] == 'Index')
    old_points = {p[0]: p for p in history['values']}
    clean = pe[np.isfinite(pe) & (pe > 0)]
    history['mean'], history['std'] = float(clean.mean()), float(clean.std())
    start = next(d for d in dates if d >= (config['attribution_start'] or dates[0]))
    earnings_start = next(d for d in dates if d >= (config['earnings_start'] or dates[0]))
    sampled = {}
    for d in dates:
        sampled[d.isocalendar()[:2]] = d
    selected = dates  # Keep exact daily benchmarks; never interpolate index levels.
    points = []
    for d in selected:
        epoch = (d - date(1970, 1, 1)).days
        p = [epoch, value('pe', d), None, None, None, None, None, None, None]
        if d >= start:
            earnings, price = change('eps12', d, start), change('price', d, start)
            multiple = (1 + price) / (1 + earnings) - 1
            p[2], p[3], p[8] = earnings + earnings * multiple / 2, multiple + earnings * multiple / 2, price
        if d >= earnings_start:
            p[4], p[5] = change('eps_fy1', d, earnings_start), change('eps_fy2', d, earnings_start)
        # Revision breadth is a constituent statistic, not a scalar index measure.
        old = old_points.get(epoch, [])
        if len(old) >= 8:
            p[6:8] = old[6:8]
        points.append(p)
    history['values'] = points
    # Rankings must use original daily index EPS, never constituent sums or
    # rounded/rebased weekly history. Missing observations stay missing.
    history['indexFYLevels'] = [
        [(d - date(1970, 1, 1)).days, value('eps_fy1', d), value('eps_fy2', d)]
        for d in dates
    ]
    history['source'] = 'Index Level'
