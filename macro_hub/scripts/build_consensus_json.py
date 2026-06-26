# -*- coding: utf-8 -*-
"""
build_consensus_json.py — Consensus(CPI/GDP) 데이터 빌더 (JSON 출력판)
원본 "Consensus Builder/CPI consensus.py","GDP consensus.py" 의 추출 로직을
importlib로 그대로 재사용 → public/data/consensus_{cpi,gdp}.json.
화면(components/Consensus.tsx)이 canvas(ridge/median)로 그린다.

median(ml) 은 토글(1M/3M/6M/12M/All)을 위해 원본 6M 대신 더 긴 윈도우로 다시 뽑는다.

실행:  python scripts/build_consensus_json.py          (엑셀 필요)
       python scripts/build_consensus_json.py --mock   (엑셀 없이 샘플)
"""
import os, sys, json, importlib.util, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
CB = os.path.join(REPO, "Consensus Builder")
OUT_DIR = os.path.join(ROOT, "public", "data")
MEDIAN_MONTHS = 24   # ml 윈도우(개월) — 토글에서 12M/All 까지 의미있게


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def long_median(mod, df, months=MEDIAN_MONTHS):
    """원본 extract_country 의 median 부분을, 더 긴 윈도우로 재계산."""
    import numpy as np, pandas as pd
    off = mod.detect_header_offset(df)
    dates = mod.parse_dates(df, off)
    dates = dates[dates.notna()]
    if len(dates) == 0:
        return []
    rows = sorted([(int(i), d) for i, d in dates.items()], key=lambda x: x[1])
    cutoff = rows[-1][1] - pd.DateOffset(months=months)
    ml = []
    for idx, d in rows:
        if d < cutoff or d.weekday() >= 5:
            continue
        v = mod.clean_numeric_values(df.iloc[idx, 1:])
        if v.size > 0:
            ml.append({"d": d.strftime("%Y-%m-%d"),
                       "med": round(float(np.median(v)), 3),
                       "q1": round(float(np.percentile(v, 25)), 3),
                       "q3": round(float(np.percentile(v, 75)), 3)})
    return ml


def build_real():
    targets = [
        ("consensus_cpi.json", os.path.join(CB, "CPI consensus.py"), "cpi_consensus"),
        ("consensus_gdp.json", os.path.join(CB, "GDP consensus.py"), "gdp_consensus"),
    ]
    for out_name, path, modname in targets:
        if not os.path.exists(path):
            print("[skip] 원본 없음:", path); continue
        mod = load_module(path, modname)
        cache = {}
        for fp in set(mod.EXCEL_FILES.values()):
            if os.path.exists(fp):
                cache[fp] = mod.open_excel_with_retry(fp)
        data = {}
        for sheet, fp in mod.EXCEL_FILES.items():
            xl = cache.get(fp)
            if xl is None or sheet not in xl.sheet_names:
                continue
            df = xl.parse(sheet, header=None)
            res = mod.extract_country(df)
            if res:
                try:
                    res["ml"] = long_median(mod, df) or res["ml"]
                except Exception as e:
                    print(f"  [warn] {sheet} long median 실패({e}) — 원본 6M 사용")
                data[sheet] = res
        bundle = {"data": data, "names": mod.COUNTRY_NAMES,
                  "generatedAt": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump(bundle, open(os.path.join(OUT_DIR, out_name), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[saved] {out_name}  ({len(data)} countries)")


def build_mock():
    import random
    random.seed(3)
    names = {"미국": "US", "영국": "UK", "일본": "JP", "독일": "DE", "유로존": "EA"}
    # 최근 24개월, 매주(목요일 가정) 한 점
    base_day = dt.date(2024, 7, 4)
    days = [(base_day + dt.timedelta(weeks=w)).isoformat() for w in range(0, 104)]  # ~24mo
    for out_name, center in [("consensus_cpi.json", 2.6), ("consensus_gdp.json", 1.8)]:
        data = {}
        for c in names:
            base = center + random.uniform(-0.4, 0.4)
            def sample(mu):
                return [round(mu + random.gauss(0, 0.18), 2) for _ in range(random.randint(8, 16))]
            two = [{"date": d, "values": sample(base + i * 0.01)} for i, d in enumerate(days[-10:])]
            six = [{"date": d, "values": sample(base + i * 0.02)} for i, d in enumerate(days[-26::2])]
            ml = []
            for i, d in enumerate(days):
                v = sorted(sample(base + i * 0.004))
                n = len(v)
                ml.append({"d": d, "med": round(v[n // 2], 3),
                           "q1": round(v[n // 4], 3), "q3": round(v[3 * n // 4], 3)})
            data[c] = {"2w": two, "6m": six, "ml": ml, "bw": 0.12}
        bundle = {"data": data, "names": names, "generatedAt": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump(bundle, open(os.path.join(OUT_DIR, out_name), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[saved-mock] {out_name}  ({len(data)} countries, ml {len(ml)}pts)")


if __name__ == "__main__":
    build_mock() if "--mock" in sys.argv else build_real()
