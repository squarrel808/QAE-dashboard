# -*- coding: utf-8 -*-
"""
build_policy_json.py - Policy Tone(hawk-dove) module data builder.
원본 ../policytone/hawkdove_dashboard.py 의 데이터 가공부를 옮겨
public/data/policy.json 으로 저장한다. (화면은 React가 담당)
실행:  python scripts/build_policy_json.py
"""
import os, json, datetime as dt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(os.path.dirname(ROOT), "policytone")
INDEX_CSV = os.path.join(SRC, "stance_index.csv")
SCORES_JSON = os.path.join(SRC, "speech_scores_full.json")
OUT = os.path.join(ROOT, "public", "data", "policy.json")
SMOOTH_WINDOW, NEUTRAL_BAND = 30, 0.15
BANK_LABEL = {"FED": "US (Fed)", "BOJ": "Japan (BOJ)", "ECB": "Eurozone (ECB)", "BOE": "UK (BoE)"}


def to_iso(v):
    s = str(v)
    return (pd.to_datetime(int(s), unit="ms") if s.isdigit() else pd.to_datetime(s)).date().isoformat()


def load_scores(path):
    """speech_scores_full.json 이 닫는 ] 없이 잘려 있어도 최대한 복구."""
    if not os.path.exists(path):
        return []
    txt = open(path, encoding="utf-8").read()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    cut = txt.rstrip(); last = cut.rfind("}")
    if last == -1:
        return []
    try:
        objs = json.loads(cut[:last + 1].rstrip().rstrip(",") + "]")
        print("[warn] scores truncated; recovered", len(objs)); return objs
    except json.JSONDecodeError:
        print("[warn] scores parse failed; no events"); return []


def main():
    idx = pd.read_csv(INDEX_CSV, encoding="utf-8-sig", parse_dates=["date"])
    scores = load_scores(SCORES_JSON)
    data = {}
    for bank, g in idx.groupby("bank"):
        g = g.sort_values("date").reset_index(drop=True)
        cov = g["coverage"].fillna(0)
        num = (g["stance"].where(cov > 0) * cov).fillna(0).rolling(SMOOTH_WINDOW, min_periods=1).sum()
        den = cov.rolling(SMOOTH_WINDOW, min_periods=1).sum()
        g["wma"] = (num / den).ffill()
        sp = g[cov > 0]
        data[bank] = {"label": BANK_LABEL.get(bank, bank),
                      "dates": [d.date().isoformat() for d in sp["date"]],
                      "bar": [round(float(v), 3) for v in sp["stance"]],
                      "trend": [round(float(v), 3) for v in sp["wma"]], "events": {}}
    for r in scores:
        bank = r.get("bank")
        if bank not in data:
            continue
        d = to_iso(r.get("date"))
        data[bank]["events"].setdefault(d, []).append({
            "sp": str(r.get("speaker") or "").strip() or "(unknown)",
            "rs": str(r.get("reasoning") or "").strip(),
            "st": round(float(r.get("stance") or 0), 2)})
    out = {"banks": data, "neutralBand": NEUTRAL_BAND, "smoothWindow": SMOOTH_WINDOW,
           "generatedAt": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("[saved]", OUT, {k: len(v["dates"]) for k, v in data.items()})


if __name__ == "__main__":
    main()
