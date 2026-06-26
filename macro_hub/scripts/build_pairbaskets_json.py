# -*- coding: utf-8 -*-
"""
build_pairbaskets_json.py — Equity Factors 모듈 데이터 빌더 (JSON 출력판)
--------------------------------------------------------------------------
기존 gs_api/build_pairbaskets.py 는 데이터+HTML을 통째로 한 파일로 구웠습니다.
이 스크립트는 '데이터만' 뽑아 public/data/pairbaskets.json 으로 저장합니다.
화면(React)은 Next.js 가 그 JSON을 읽어 그립니다. (관심사 분리)

쓰는 법:
  1) gs_api/.env (GS_CLIENT_ID / GS_CLIENT_SECRET) 와
     gs_api/pair_baskets_shortlist.csv, sector_factor_grid.csv 를 사용합니다.
  2) python scripts/build_pairbaskets_json.py
  3) 생성된 JSON을 git push 하면 Vercel이 자동 재배포 → 사이트 데이터 갱신.

GS 패키지/인증이 없으면(예: 로컬 미설치) --mock 으로 샘플 JSON을 만듭니다:
  python scripts/build_pairbaskets_json.py --mock
"""
import os, csv, json, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # macro_hub/
GS_DIR = os.path.join(os.path.dirname(ROOT), "gs_api")   # ../gs_api
OUT = os.path.join(ROOT, "public", "data", "pairbaskets.json")


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def series_monthly(sub):
    import pandas as pd
    s = sub.set_index("date")["closePrice"].sort_index()
    m = s.groupby(s.index.to_period("M")).last().dropna()
    return [str(p) for p in m.index], [round(float(x), 4) for x in m.values]


def build_real():
    import pandas as pd
    from dotenv import load_dotenv
    from gs_quant.session import GsSession, Environment
    from gs_quant.data import Dataset

    load_dotenv(os.path.join(GS_DIR, ".env"))
    cid, csec = os.getenv("GS_CLIENT_ID"), os.getenv("GS_CLIENT_SECRET")
    if not cid or not csec:
        raise SystemExit("gs_api/.env 에 GS_CLIENT_ID / GS_CLIENT_SECRET 필요")
    GsSession.use(Environment.PROD, cid, csec, ("read_product_data",))

    short = read_csv(os.path.join(GS_DIR, "pair_baskets_shortlist.csv"))
    grid = read_csv(os.path.join(GS_DIR, "sector_factor_grid.csv"))
    bbids = sorted({r["bbid"] for r in short} | {r["bbid"] for r in grid})

    df = Dataset("PAIR_BASKETS_LEVELS").get_data(dt.date(2012, 1, 1), dt.date.today(), bbid=bbids)
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])
    series = {b: series_monthly(sub) for b, sub in df.groupby("bbid")}

    data = {"groups": {}, "sector": {}}
    for r in short:
        b = r["bbid"]
        if b in series:
            d, c = series[b]
            data["groups"].setdefault(r["group"], []).append({"label": r["label"], "bbid": b, "dates": d, "close": c})

    sectors, factors, items = [], [], []
    for r in grid:
        if r["sector"] not in sectors: sectors.append(r["sector"])
        if r["factor"] not in factors: factors.append(r["factor"])
        b = r["bbid"]
        if b in series:
            d, c = series[b]
            items.append({"sector": r["sector"], "factor": r["factor"], "bbid": b, "dates": d, "close": c})
    data["sector"] = {"sectors": sectors, "factors": factors, "items": items}
    return data


def build_mock():
    import math, random
    random.seed(7)
    sectors = ["Technology", "Financials", "Energy", "Health Care", "Industrials"]
    factors = ["Growth", "Value", "Momentum", "Quality", "Low Vol"]
    months = [f"{y}-{m:02d}" for y in range(2021, 2026) for m in range(1, 13)][:54]

    def walk(drift):
        lvl, out = 100.0, []
        for _ in months:
            lvl *= math.exp(drift + random.gauss(0, 0.03))
            out.append(round(lvl, 4))
        return out

    items = []
    for s in sectors:
        for f in factors:
            items.append({"sector": s, "factor": f, "bbid": f"{s[:3]}{f[:3]}".upper(),
                          "dates": months, "close": walk(random.uniform(-0.01, 0.015))})
    groups = {"Factor": [{"label": f, "bbid": f.upper(), "dates": months, "close": walk(random.uniform(-0.01, 0.02))} for f in factors],
              "Tech": [{"label": t, "bbid": t.upper(), "dates": months, "close": walk(random.uniform(-0.01, 0.02))}
                       for t in ["AI", "Software vs Semis", "Mega vs Nonprof Tech"]]}
    return {"groups": groups, "sector": {"sectors": sectors, "factors": factors, "items": items}}


def main():
    mock = "--mock" in sys.argv
    data = build_mock() if mock else build_real()
    data["generatedAt"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    kind = "MOCK 샘플" if mock else "GS 실데이터"
    print(f"[저장] {OUT}  ({kind}, 섹터셀 {len(data['sector']['items'])}개)")


if __name__ == "__main__":
    main()
