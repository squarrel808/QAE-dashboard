# fill_preprocess_rules.py
"""
fetch 이후, Meta data_Raw data.xlsx 의 '전처리' 시트에 빠진 행을 채운다.

전처리 시트는 지표마다 level / diffusion 중 하나를 지정한다:
  level     = 수준 지표 → 성장률로 변환 (YoY: 12개월 로그차분 / Mom: 3mma의 3개월 로그차분)
  diffusion = 서베이·비율 지표 → 그대로 사용 (Mom: 3mma 차분)

이 행이 없으면 pca_gdp.py 가 에러 없이 WARN만 찍고 지표를 조용히 제외한다.

분류는 Metadata 의 datatype 을 1차 근거로 하고, descriptor 키워드로 보정한다.
확신이 낮은 건은 REVIEW 로 분리해 사람이 보게 한다 — 자동으로 밀어넣지 않는다.

실행:
  python fill_preprocess_rules.py            # 분류 결과만 출력 (기본: 쓰지 않음)
  python fill_preprocess_rules.py --write     # 확신 높은 건만 전처리 시트에 추가
  python fill_preprocess_rules.py --write-all # REVIEW 건도 제안값으로 추가

  python fill_preprocess_rules.py --from-confirmed
      fetch 이전에 tickerlist_confirmed.xlsx 의 지표명(괄호 안 단위)만으로 초안을 만든다.
      fetch 후 실제 datatype 으로 다시 돌리면 더 정확하므로, 초안 검토용으로만 쓸 것.
      결과는 preprocess_draft.csv 로 저장된다.
"""
import re
import sys
import shutil
from pathlib import Path

import pandas as pd

BASE        = Path(__file__).resolve().parent
DATA_FILE   = BASE / "Meta data_Raw data.xlsx"
CONFIRMED   = BASE / "tickerlist_confirmed.xlsx"
TICKERS     = BASE / "tickers.xlsx"
DRAFT_CSV   = BASE / "preprocess_draft.csv"
SHEET       = "전처리"

# ── datatype → 규칙 (소문자 부분일치, 위에서부터 먼저 맞는 것) ─────────────
# 통화·물량·인원 등 '수준'은 성장률 변환이 필요하고,
# 확산지수·%Bal 같은 서베이 밸런스는 이미 변화율 성격이라 그대로 쓴다.
DATATYPE_RULES = [
    ("%bal",      "diffusion", "서베이 밸런스"),
    ("bal",       "diffusion", "서베이 밸런스"),
    ("ratio",     "diffusion", "배율 — 수준 그대로 사용"),
    ("loccur",    "level",     "현지통화 금액"),
    ("mil.",      "level",     "통화 금액"),
    ("bil.",      "level",     "통화 금액"),
    ("thous",     "level",     "물량/인원"),
    ("units",     "level",     "물량"),
    ("persons",   "level",     "인원"),
    ("us$",       "level",     "통화 금액"),
    ("eur",       "level",     "통화 금액"),
    ("yen",       "level",     "통화 금액"),
    ("gbp",       "level",     "통화 금액"),
    ("a$",        "level",     "통화 금액"),
    ("c$",        "level",     "통화 금액"),
    ("chn",       "level",     "실질(연쇄) 금액"),
]

# descriptor 안의 '결정적' 단서 — 지표명(orders/production 등)보다 먼저 본다.
# ISM/PMI 계열은 이름에 Orders·Production 이 들어가지만 실제로는 확산지수라서,
# 이 마커를 뒤에 두면 level 로 오분류된다. (역검증에서 실제로 6건 틀렸던 원인)
DESC_DIFFUSION_STRONG = [
    "50+", "50 =", "50=",        # PMI 관례: 50 = 경기 중립선
    "+=",                        # "(+=Growth Above Trend)" 시카고연은 CNAI 등
    "%bal", "diffusion index",
    "all good = 100",            # NAHB 주택시장지수
]

# 서베이 발행기관·시리즈 이름. 여기서 나온 지표는 이름에 Orders/Production/Employment 가
# 들어가도 실제로는 밸런스·확산지수다. 확정판 지표명은 단위가 잘려 있는 경우가 많아
# (예: 'Philly Fed: Future Capital Expenditures (SA)') 이 목록이 사실상 유일한 단서가 된다.
DESC_SURVEY_HOUSE = [
    "philly fed", "philadelphia fed", "richmond fed", "empire state", "empire st",
    "kc fed", "kansas city fed", "dallas fed", "chicago fed", "cfnai",
    "ism mfg", "ism ", "napm", "nfib", "conference board", "cb:",
    "ifo", "zew", "sentix", "gfk", "insee", "istat",
    "nab business survey", "westpac", "roy morgan",
    "cfib", "ivey", "nanos",
    "boe agents", "cbi ", "rics", "lloyds", "make uk",
    "tankan", "economic watchers", "shoko chukin", "teikoku",
    "business barometer", "business survey", "business outlook",
    "business climate", "business conditions", "business confidence",
]

# 서베이 성격의 이름 — 기준연도 지수(1985=100)라도 확산지수로 취급
DESC_DIFFUSION = [
    "pmi", "diffusion", "sentiment", "confidence", "outlook", "expectations",
    "survey", "balance", "climate", "barometer", "market index",
    "business conditions", "business barometer", "intentions",
    "unemployment rate", "utilization", "% of ", "hard to get", "jobs hard",
    "percent planning", "time to buy",
]

# 수량·금액 성격의 이름 — 성장률 변환 대상
DESC_LEVEL = [
    "production", "shipments", "orders", "starts", "permits", "approvals",
    "sales", "exports", "imports", "employment:", "employed", "payrolls",
    "earnings", "income", "openings", "turnover", "floor space", "vacancies",
    # 서베이 기관이 만들지만 실제로는 '건수' 지수 — 밸런스가 아니라 수량이다
    "job ads", "job advertisements",
]

VALID = ("level", "diffusion")


def classify(datatype, descriptor):
    """returns (rule, confidence, reason). confidence: 'high' | 'review'"""
    dt = str(datatype).strip().lower()
    ds = str(descriptor).strip().lower()

    # 0) descriptor 의 결정적 단서가 최우선 — 지표명·datatype 보다 강하다
    for kw in DESC_DIFFUSION_STRONG:
        if kw in ds:
            return "diffusion", "high", f"'{kw}' — 확산지수 표기"

    # 0-b) 서베이 발행기관 이름 — 단, 실제 통화·물량 단위가 붙어 있으면 진짜 수량이므로 제외
    if not any(k in dt for k in ("mil.", "bil.", "thous", "units", "persons")):
        for kw in DESC_SURVEY_HOUSE:
            if kw in ds:
                return "diffusion", "high", f"'{kw}' — 서베이 발행기관"

    # 1) 명확한 서베이 밸런스 / 통화·물량 단위
    for key, rule, why in DATATYPE_RULES:
        if key in dt:
            return rule, "high", f"datatype '{datatype}' → {why}"

    # 2) 서베이성 이름이면 단위와 무관하게 diffusion
    #    (예: Consumer Confidence 는 1985=100 기준연도 지수지만 확산지수로 다룬다)
    for kw in DESC_DIFFUSION:
        if kw in ds:
            return "diffusion", "high", f"'{kw}' — 서베이 지표"

    # 3) % 계열: 위에서 안 걸렸으면 rate 인지 판단이 필요
    if dt in ("%", "pct", "percent") or dt.startswith("%"):
        return "diffusion", "review", "datatype '%' — rate/diffusion 구분 확인 필요"

    # 4) INDEX 는 기준연도 지수(level)와 확산지수(diffusion)가 섞여 있다
    if "index" in dt:
        for kw in DESC_LEVEL:
            if kw in ds:
                return "level", "high", f"INDEX + '{kw}' — 실물 수량 지수"
        return "level", "review", "INDEX — 기준연도지수(level)인지 확산지수인지 확인 필요"

    # 5) datatype 이 비었거나 모르는 값 → descriptor 로만
    for kw in DESC_LEVEL:
        if kw in ds:
            return "level", "review", f"datatype 불명 + '{kw}'"
    return "level", "review", f"datatype '{datatype}' 미분류 — 확인 필요"


def nonpositive_series():
    """Wide 시트에서 0 이하 값이 있는 지표 → {ticker_pk: 개수}.

    Wide 헤더는 'CODE@DATABASE'(예: AP2Y@UK) 또는 descriptor 로 올 수 있어서
    양쪽 다 ticker_pk 로 정규화한다. pca_gdp.load_data 도 같은 변환을 한다.
    """
    try:
        wide = pd.read_excel(DATA_FILE, sheet_name="Wide")
        meta = pd.read_excel(DATA_FILE, sheet_name="Metadata")
    except Exception:
        return {}

    # descriptor(헤더) → ticker_pk. 중복 descriptor 는 '... (pk)' 로 병기돼 있다.
    rev = {}
    for _, r in meta.iterrows():
        pk = str(r["ticker_pk"])
        desc = str(r.get("descriptor", "")).strip()
        if desc:
            rev.setdefault(desc, pk)
            rev[f"{desc} ({pk})"] = pk

    out = {}
    for col in wide.columns[1:]:
        pk = rev.get(str(col)) or ticker_to_pk(col)
        s = pd.to_numeric(wide[col], errors="coerce").dropna()
        if s.empty:
            continue
        n = int((s <= 0).sum())
        if n:
            out[pk] = n
    return out


def ticker_to_pk(t):
    s = str(t).strip()
    if "@" in s:
        code, db = s.split("@", 1)
        return f"{db.strip().lower()}:{code.strip().lower()}"
    return s.lower()


def unit_hint(name):
    """지표명 끝 괄호에서 단위를 뽑는다. '... (SA, Mil.A$)' → 'SA, Mil.A$'
       fetch 이전에는 Haver datatype 이 없으므로 이걸 대신 쓴다."""
    groups = re.findall(r"\(([^()]*)\)", str(name))
    return groups[-1] if groups else ""


def draft_from_confirmed():
    """fetch 이전: 확정판 지표명만으로 level/diffusion 초안 생성."""
    tick = pd.read_excel(TICKERS)                       # 이미 필터링된 최종 티커
    keep = set(tick["Ticker"].astype(str).str.strip())

    xl = pd.ExcelFile(CONFIRMED)
    rows = []
    for s in xl.sheet_names:
        if s == "읽어줘":
            continue
        df = xl.parse(s)
        for _, r in df.iterrows():
            t = str(r.get("Ticker", "")).strip()
            if t not in keep:
                continue
            name = str(r.get("지표명", "")).strip()
            hint = unit_hint(name)
            rule, conf, why = classify(hint, name)
            rows.append({"ticker_pk": ticker_to_pk(t), "Ticker": t,
                         "country": s.upper(), "category": str(r.get("카테고리", "")).strip().lower(),
                         "rule": rule, "conf": conf, "why": why,
                         "unit": hint, "지표명": name})

    prop = pd.DataFrame(rows).drop_duplicates(subset=["ticker_pk"], keep="first")

    # 이미 전처리 시트에 있는 건 사람이 정한 값이므로 그대로 두고 표시만 한다
    try:
        pre = pd.read_excel(DATA_FILE, sheet_name=SHEET)
        known = dict(zip(pre["ticker_pk"].astype(str),
                         pre.iloc[:, -1].astype(str).str.strip().str.lower()))
    except Exception:
        known = {}
    prop["기존"] = prop["ticker_pk"].map(known).fillna("")
    prop["일치"] = [("" if not k else ("O" if k == r else "X"))
                    for k, r in zip(prop["기존"], prop["rule"])]

    print(f"티커 {len(prop)}개 — 기존 전처리 보유 {(prop['기존']!='').sum()}개 / 신규 {(prop['기존']=='').sum()}개")
    mismatch = prop[prop["일치"] == "X"]
    if len(mismatch):
        print(f"[WARN] 기존 값과 다른 제안 {len(mismatch)}건:")
        for _, r in mismatch.iterrows():
            print(f"  {r['ticker_pk']:26s} 기존={r['기존']:9s} 제안={r['rule']:9s} {r['지표명'][:50]}")
    print()

    new = prop[prop["기존"] == ""]
    for cc in ["US", "AU", "CA", "DE", "JP", "UK"]:
        sub = new[new["country"] == cc]
        if sub.empty:
            continue
        nl = (sub["rule"] == "level").sum()
        nd = (sub["rule"] == "diffusion").sum()
        print(f"===== {cc} — {len(sub)}건 (level {nl} / diffusion {nd}) =====")
        for _, r in sub.sort_values(["category", "rule"]).iterrows():
            mark = "★" if r["conf"] == "review" else " "
            print(f" {mark}{r['category']:9s} {r['rule']:9s} {r['Ticker']:22s} "
                  f"[{r['unit'][:22]:22s}] {r['지표명'][:52]}")
        print()

    rev = new[new["conf"] == "review"]
    print(f"요약: 신규 {len(new)}건 = level {(new['rule']=='level').sum()} / "
          f"diffusion {(new['rule']=='diffusion').sum()}   |   ★확인필요 {len(rev)}건")
    if len(rev):
        print("\n--- ★ 확인 필요 ---")
        for _, r in rev.sort_values(["country", "category"]).iterrows():
            print(f"  {r['country']} {r['category']:9s} {r['rule']:9s} {r['Ticker']:22s} {r['지표명'][:48]}")
            print(f"        └ {r['why']}")

    prop.to_csv(DRAFT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n저장: {DRAFT_CSV}")
    return 0


def main():
    if "--from-confirmed" in sys.argv:
        return draft_from_confirmed()

    write     = "--write" in sys.argv
    write_all = "--write-all" in sys.argv

    meta = pd.read_excel(DATA_FILE, sheet_name="Metadata")
    pre  = pd.read_excel(DATA_FILE, sheet_name=SHEET)

    rule_col = pre.columns[-1]                      # 보통 'Unnamed: 2'
    have = set(pre["ticker_pk"].astype(str))

    missing = meta[~meta["ticker_pk"].astype(str).isin(have)].copy()
    extra   = sorted(have - set(meta["ticker_pk"].astype(str)))

    print(f"Metadata {len(meta)}개 / 전처리 {len(pre)}개 → 누락 {len(missing)}개")
    if extra:
        print(f"[INFO] 전처리에만 있고 Metadata엔 없는 행 {len(extra)}개 (옛 티커 잔여): {extra}")
    print()

    if missing.empty:
        print("채울 것 없음.")
        return 0

    # level 은 np.log(x).diff() 를 거치므로 0·음수가 섞이면 전 구간이 NaN 이 된다.
    # 키워드로 추측하지 말고 실제 데이터로 확인해서 강제로 diffusion 으로 돌린다.
    nonpos = nonpositive_series()

    recs = []
    for _, r in missing.iterrows():
        pk = str(r["ticker_pk"])
        rule, conf, why = classify(r.get("datatype", ""), r.get("descriptor", ""))
        if rule == "level" and pk in nonpos:
            rule, conf = "diffusion", "review"
            why = f"0·음수 {nonpos[pk]}개 포함 — 로그차분 불가라 level 불가"
        recs.append({"ticker_pk": pk, "code": r.get("code", ""),
                     "rule": rule, "conf": conf, "why": why,
                     "datatype": r.get("datatype", ""),
                     "category": r.get("category", ""),
                     "country": r.get("country", ""),
                     "descriptor": str(r.get("descriptor", ""))[:60]})
    prop = pd.DataFrame(recs)

    for conf in ("high", "review"):
        sub = prop[prop["conf"] == conf]
        if sub.empty:
            continue
        head = "자동 분류 (확신 높음)" if conf == "high" else "★ 사람이 확인 필요"
        print(f"--- {head} — {len(sub)}건 ---")
        for _, r in sub.sort_values(["country", "category", "ticker_pk"]).iterrows():
            print(f"  {r['country']:5s} {r['category']:9s} {r['rule']:9s} "
                  f"{r['ticker_pk']:26s} [{r['datatype']}] {r['descriptor']}")
            if conf == "review":
                print(f"        └ {r['why']}")
        print()

    print(f"요약: level {(prop['rule']=='level').sum()} / diffusion {(prop['rule']=='diffusion').sum()}"
          f"  |  확신 {(prop['conf']=='high').sum()} / 확인필요 {(prop['conf']=='review').sum()}")

    if not (write or write_all):
        print("\n(쓰지 않음. --write 로 확신 높은 건만, --write-all 로 전부 추가)")
        return 0

    add = prop if write_all else prop[prop["conf"] == "high"]
    if add.empty:
        print("\n추가할 행 없음.")
        return 0

    new_rows = pd.DataFrame({"ticker_pk": add["ticker_pk"].values,
                             "code": add["code"].values,
                             rule_col: add["rule"].values})
    merged = pd.concat([pre, new_rows], ignore_index=True)

    bad = merged[~merged[rule_col].astype(str).str.strip().str.lower().isin(VALID)]
    if len(bad):
        print(f"\n[중단] level/diffusion 아닌 값이 있습니다:\n{bad.to_string()}")
        return 1

    backup = DATA_FILE.with_suffix(".xlsx.bak")
    shutil.copy2(DATA_FILE, backup)
    with pd.ExcelWriter(DATA_FILE, engine="openpyxl", mode="a",
                        if_sheet_exists="replace") as wr:
        merged.to_excel(wr, sheet_name=SHEET, index=False)

    print(f"\n백업: {backup}")
    print(f"전처리 시트 {len(pre)} → {len(merged)}행")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
