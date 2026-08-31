# prune_stale.py
"""
tickers.xlsx 에서 빠진 티커의 잔여물을 Meta data_Raw data.xlsx / last_dates.json 에서 제거한다.

fetch 는 Metadata 시트를 tickers.xlsx 기준으로 다시 만들지만,
Wide 시트와 전처리 시트, last_dates.json 에는 옛 티커가 그대로 남는다.
pca_gdp 는 category 가 없는 컬럼을 WARN 후 버리므로 결과에 영향은 없지만
파일이 계속 불어나고 로그가 지저분해진다.

티커를 뺀 뒤 Haver 를 다시 호출하지 않고 정리하고 싶을 때도 이걸 쓴다
(Metadata 에서도 지워지므로 pca_gdp 가 즉시 제외한다).

실행:
  python prune_stale.py           # 무엇이 지워질지 보여주기만 함
  python prune_stale.py --write   # 실제로 정리 (원본은 .bak 로 백업)
"""
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

BASE       = Path(__file__).resolve().parent
DATA_FILE  = BASE / "Meta data_Raw data.xlsx"
TICKERS    = BASE / "tickers.xlsx"
STATE_FILE = BASE / "last_dates.json"


def ticker_to_pk(t):
    s = str(t).strip()
    if "@" in s:
        code, db = s.split("@", 1)
        return f"{db.strip().lower()}:{code.strip().lower()}"
    return s.lower()


def main():
    write = "--write" in sys.argv

    keep = {ticker_to_pk(t) for t in pd.read_excel(TICKERS)["Ticker"].dropna()}
    print(f"tickers.xlsx 유효 티커: {len(keep)}개\n")

    sheets = pd.read_excel(DATA_FILE, sheet_name=None)
    wide, meta, pre = sheets["Wide"], sheets["Metadata"], sheets["전처리"]

    # Wide: 첫 컬럼은 날짜. 헤더는 'CODE@DATABASE' 또는 descriptor 로 올 수 있다.
    desc2pk = {str(r["descriptor"]).strip(): str(r["ticker_pk"])
               for _, r in meta.iterrows() if str(r.get("descriptor", "")).strip()}
    drop_cols = []
    for c in wide.columns[1:]:
        pk = desc2pk.get(str(c)) or ticker_to_pk(c)
        if pk not in keep:
            drop_cols.append((c, pk))

    # 파생 지표(formula 있는 행)는 Haver 티커가 아니라 tickers.xlsx 에 없다 — 지우면 안 된다.
    if "formula" in pre.columns:
        derived = pre["formula"].astype(str).str.strip().replace("nan", "").ne("")
    else:
        derived = pd.Series(False, index=pre.index)

    drop_meta = meta[~meta["ticker_pk"].astype(str).isin(keep)]
    drop_pre  = pre[~pre["ticker_pk"].astype(str).isin(keep) & ~derived]

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    drop_state = [k for k in state if ticker_to_pk(k) not in keep]

    print(f"Wide     {len(wide.columns)-1} → {len(wide.columns)-1-len(drop_cols)}  (제거 {len(drop_cols)})")
    for c, pk in drop_cols:
        print(f"    - {str(c)[:60]}  [{pk}]")
    print(f"Metadata {len(meta)} → {len(meta)-len(drop_meta)}  (제거 {len(drop_meta)})")
    for _, r in drop_meta.iterrows():
        print(f"    - {r['ticker_pk']:26s} {str(r.get('descriptor',''))[:52]}")
    print(f"전처리   {len(pre)} → {len(pre)-len(drop_pre)}  (제거 {len(drop_pre)})")
    for _, r in drop_pre.iterrows():
        print(f"    - {r['ticker_pk']}")
    print(f"last_dates.json {len(state)} → {len(state)-len(drop_state)}  (제거 {len(drop_state)})")

    missing = keep - set(meta["ticker_pk"].astype(str))
    if missing:
        print(f"\n[WARN] tickers.xlsx 에 있는데 Metadata 에 없음 {len(missing)}개 — fetch 필요: {sorted(missing)}")

    if not write:
        print("\n(--write 를 붙여야 실제로 정리됩니다)")
        return 0

    if not (drop_cols or len(drop_meta) or len(drop_pre) or drop_state):
        print("\n정리할 것 없음.")
        return 0

    backup = DATA_FILE.with_suffix(".xlsx.prune.bak")
    shutil.copy2(DATA_FILE, backup)

    sheets["Wide"]     = wide.drop(columns=[c for c, _ in drop_cols])
    sheets["Metadata"] = meta[meta["ticker_pk"].astype(str).isin(keep)].reset_index(drop=True)
    sheets["전처리"]   = pre[pre["ticker_pk"].astype(str).isin(keep)].reset_index(drop=True)

    with pd.ExcelWriter(DATA_FILE, engine="openpyxl", mode="w") as wr:
        for name, df in sheets.items():
            df.to_excel(wr, sheet_name=name, index=False)

    for k in drop_state:
        state.pop(k, None)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n백업: {backup}")
    print("정리 완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
