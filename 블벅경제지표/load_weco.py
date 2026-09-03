# -*- coding: utf-8 -*-
"""
load_weco.py — 블룸버그 WECO 내보내기(xlsx) → 대시보드용 행(row) 리스트
--------------------------------------------------------------------
입력 : 이 파일과 같은 폴더의 `*_eco.xlsx`  (보통 2개씩 떨궈 넣음)
         - '지표' 파일        (Survey/Actual/Prior/Relevance 가 채워져 있음)
         - '연설·이벤트' 파일 (Survey/Actual 비어 있고 Relevance=0)
       파일명은 매번 바뀌므로 이름으로 구분하지 않는다. 내용으로 판별한다.
       최근 MERGE_DAYS 안에 들어온 파일을 전부(최대 MAX_FILES개) 읽어 종류별로
       합치되, 같은 일정(날짜·시각·국가·이벤트)이 겹치면 **최신 파일 값**을 쓴다.
       한 개만 새로 떨궈 넣어도 이전 세트가 그대로 살아 있어 날짜가 안 끊긴다.

출력 : load_rows() → list[dict]
       {"d","t","cc","flag","ev","p","svy","act","pri","rev","rel","kind"}
       (weco_dashboard.py 가 쓰던 스키마 + kind 필드)

실행 : python load_weco.py       # 선택된 파일 / 판별 결과 / 행 수 요약 출력
"""
import io
import os
import re
import sys
import glob
import datetime as dt

import pandas as pd

# Windows cp949 콘솔에서 이모지·한글 출력하다 죽지 않게
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                    # 재설정 불가 환경 대비
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
PATTERN = os.path.join(BASE, "*_eco.xlsx")
N_FILES = 2                                          # 한 세트 = 지표 1 + 이벤트 1
MAX_FILES = 6                                        # 한 번에 읽을 최대 파일 수
MERGE_DAYS = 14                                      # 최신 파일 기준 이 일수 안의 것만 병합

# --- 국가 매핑 -------------------------------------------------------------
# weco_dashboard.py 와 동일한 기본 매핑 (그쪽 파일은 건드리지 않는다)
FLAG = {"US": "\U0001F1FA\U0001F1F8", "GE": "\U0001F1E9\U0001F1EA", "CA": "\U0001F1E8\U0001F1E6",
        "AU": "\U0001F1E6\U0001F1FA", "UK": "\U0001F1EC\U0001F1E7", "FR": "\U0001F1EB\U0001F1F7",
        "JN": "\U0001F1EF\U0001F1F5"}
DISP = {"US": "US", "GE": "DE", "CA": "CA", "AU": "AU", "UK": "UK", "FR": "FR", "JN": "JP"}

# 실제 파일에 나오지만 위 기본 매핑에 없던 블룸버그 코드 보충.
# (이 블록을 지우면 해당 국가들도 '코드 그대로 + 지구본' 으로 표시된다)
FLAG.update({
    "IT": "\U0001F1EE\U0001F1F9", "RU": "\U0001F1F7\U0001F1FA", "EC": "\U0001F1EA\U0001F1FA",
    "CH": "\U0001F1E8\U0001F1F3", "SZ": "\U0001F1E8\U0001F1ED", "SP": "\U0001F1EA\U0001F1F8",
    "NE": "\U0001F1F3\U0001F1F1", "SW": "\U0001F1F8\U0001F1EA", "NO": "\U0001F1F3\U0001F1F4",
    "DE": "\U0001F1E9\U0001F1F0", "FI": "\U0001F1EB\U0001F1EE", "IR": "\U0001F1EE\U0001F1EA",
    "PO": "\U0001F1F5\U0001F1F9", "GR": "\U0001F1EC\U0001F1F7", "BE": "\U0001F1E7\U0001F1EA",
    "OE": "\U0001F1E6\U0001F1F9", "SK": "\U0001F1F0\U0001F1F7", "NZ": "\U0001F1F3\U0001F1FF",
    "MX": "\U0001F1F2\U0001F1FD", "BZ": "\U0001F1E7\U0001F1F7", "IN": "\U0001F1EE\U0001F1F3",
    "TU": "\U0001F1F9\U0001F1F7", "PL": "\U0001F1F5\U0001F1F1", "CZ": "\U0001F1E8\U0001F1FF",
    "HU": "\U0001F1ED\U0001F1FA", "SA": "\U0001F1FF\U0001F1E6", "ID": "\U0001F1EE\U0001F1E9",
    "TA": "\U0001F1F9\U0001F1FC", "HK": "\U0001F1ED\U0001F1F0", "SI": "\U0001F1F8\U0001F1EC",
})
DISP.update({
    "EC": "EZ", "CH": "CN", "SZ": "CH", "SP": "ES", "NE": "NL", "SW": "SE", "DE": "DK",
    "IR": "IE", "PO": "PT", "OE": "AT", "SK": "KR", "BZ": "BR", "TU": "TR", "SA": "ZA",
    "TA": "TW", "SI": "SG",
})
GLOBE = "\U0001F310"

NULLS = {"", "--", "---", "-", "n/a", "na", "nan", "nat", "none", "null", "#n/a"}
DATE_RANGE = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*\d")
HAS_TIME = re.compile(r"\d{1,2}:\d{2}")


# --- 값 유틸 ---------------------------------------------------------------
def _blank(v):
    """블룸버그식 '값 없음' 판정: NaN / 빈칸 / 공백만 / '--'."""
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip().lower() in NULLS


def fmt(v):
    """weco_dashboard.fmt() 와 같은 표시 포맷.
    값 없음 -> '', |v|<1 인 소수는 % 환산, |v|>=1000 -> 천단위 콤마 정수,
    그 외 숫자 -> 유효숫자 4자리.
    '16.30m' / '$159.3b' 처럼 단위가 붙은 문자열은 원문 유지.

    % 환산은 블룸버그가 MoM/YoY 를 소수(-0.003)로 내보내기 때문이다.
    이걸 그대로 두면 화면에 '-0.003' 으로 나와 읽기 나쁘다 — 기존 대시보드와
    동일하게 '-0.3%' 로 보여준다. 현재 세트 550행 중 308행이 여기 해당한다."""
    if _blank(v):
        return ""
    if isinstance(v, str):
        return v.strip()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v).strip()
    if f != f:                                       # NaN
        return ""
    if f == 0:
        return "0"
    if abs(f) < 1:
        return "{:.1f}%".format(f * 100)
    if abs(f) >= 1000:
        return "{:,.0f}".format(f)
    return "{:.4g}".format(f)


def _parse_when(v):
    """Date Time -> ('YYYY-MM-DD', 'HH:MM'). 실패하면 (None, None).
    '9/23/2026-9/30/2026' 같은 기간 표기는 시작일만 쓰고 시각은 비운다."""
    if _blank(v):
        return None, None
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.strftime("%Y-%m-%d"), v.strftime("%H:%M")
    raw = str(v).strip()
    m = DATE_RANGE.match(raw)
    s = m.group(1) if m else raw
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        return None, None
    # 시각이 안 적힌 행(기간 표기 등)은 시간 칸을 비워 둔다
    return ts.strftime("%Y-%m-%d"), (ts.strftime("%H:%M") if HAS_TIME.search(raw) else "")


def _period(v):
    if _blank(v):
        return ""
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.strftime("%m/%d")
    return str(v).strip()


# --- 파일 선택 -------------------------------------------------------------
def pick_files(n=None):
    """읽을 파일들을 최신순으로. 수정시각 우선, 같으면 파일명(=내보낸 시각) 순.

    n 을 주면 그 개수만. 안 주면 '가장 최신 파일에서 MERGE_DAYS 안'에 들어온 것만
    최대 MAX_FILES 개. 옛날에 넣어둔 파일은 이 창 밖이라 자동으로 빠진다.
    """
    files = [f for f in glob.glob(PATTERN) if not os.path.basename(f).startswith("~$")]
    files.sort(key=lambda f: (os.path.getmtime(f), os.path.basename(f)), reverse=True)
    if n is not None:
        return files[:n]
    if not files:
        return files
    newest = os.path.getmtime(files[0])
    cut = newest - MERGE_DAYS * 86400
    return [f for f in files if os.path.getmtime(f) >= cut][:MAX_FILES]


def _read(path):
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def classify(df):
    """지표('ind') / 이벤트('evt') 판별. 파일명이 아니라 내용으로만 본다.
    반환: (kind, score, 진단문자열)"""
    n = max(len(df), 1)
    svy = df["Survey"] if "Survey" in df.columns else pd.Series(dtype=object)
    act = df["Actual"] if "Actual" in df.columns else pd.Series(dtype=object)
    if "Relevance" in df.columns:
        rel = pd.to_numeric(df["Relevance"], errors="coerce").fillna(0)
    else:
        rel = pd.Series([0.0])
    svy_ratio = sum(0 if _blank(v) else 1 for v in svy) / n
    act_ratio = sum(0 if _blank(v) else 1 for v in act) / n
    rel_mean = float(rel.mean()) if len(rel) else 0.0
    score = 0.4 * svy_ratio + 0.2 * act_ratio + 0.4 * (rel_mean / 100.0)
    kind = "ind" if score >= 0.20 else "evt"
    diag = "survey {:.0%} / actual {:.0%} / rel평균 {:.1f} -> score {:.3f}".format(
        svy_ratio, act_ratio, rel_mean, score)
    return kind, score, diag


# --- 메인 ------------------------------------------------------------------
def load_rows(verbose=True):
    """가장 최근 세트(지표+이벤트)를 읽어 대시보드용 행 리스트를 돌려준다."""
    paths = pick_files()
    if not paths:
        raise FileNotFoundError(PATTERN + " 에 해당하는 파일이 없습니다")

    frames = []
    for p in paths:
        df = _read(p)
        kind, score, diag = classify(df)
        frames.append([p, df, kind, score, diag])

    # 파일이 딱 2개인데 둘 다 같은 종류로 판정되면 상대비교로 갈라준다
    # (한 세트를 같은 종류로 두 번 내보낸 경우. 3개 이상이면 점수 그대로 믿는다 —
    #  지표 파일 2개 + 이벤트 1개 같은 정상 조합을 억지로 갈라놓지 않기 위해서다)
    if len(frames) == 2 and frames[0][2] == frames[1][2]:
        hi, lo = (0, 1) if frames[0][3] >= frames[1][3] else (1, 0)
        frames[hi][2], frames[lo][2] = "ind", "evt"
        for f in frames:
            f[4] += "  [동점 판정 -> 상대비교로 재분류]"

    # frames 는 최신순이다. 같은 일정이 여러 파일에 있으면 먼저 만난(=최신) 값을 쓴다.
    rows, stat, seen = [], [], set()
    for p, df, kind, _score, diag in frames:
        kept = dropped = skipped = dup = 0
        for _, r in df.iterrows():
            ev = "" if _blank(r.get("Event")) else str(r.get("Event")).strip()
            if not ev or ev.lower() == "event":
                skipped += 1                          # 빈 줄 / 'Download time:' 꼬리 / 반복 헤더
                continue
            d, t = _parse_when(r.get("Date Time"))
            if not d:
                skipped += 1
                continue
            cc = "" if _blank(r.get("Country Code")) else str(r.get("Country Code")).strip().upper()
            key = (d, t, cc, ev)
            if key in seen:                           # 더 최신 파일에서 이미 가져온 일정
                dup += 1
                continue
            # 지표 파일은 컨센서스(Survey) 있는 행만. 이벤트 파일은 전부.
            if kind == "ind" and _blank(r.get("Survey")):
                dropped += 1
                continue
            # 실제로 담은 행만 seen 에 넣는다. 컨센서스가 비어 빠진 행까지 잡아두면
            # 같은 일정이 옛 파일(또는 이벤트 파일)에 살아 있어도 통째로 사라진다.
            seen.add(key)
            try:
                rel = float(r.get("Relevance"))
            except (TypeError, ValueError):
                rel = 0.0
            if rel != rel:
                rel = 0.0
            rows.append({
                "d": d,
                "t": t,
                "cc": DISP.get(cc, cc),
                "flag": FLAG.get(cc, GLOBE),
                "ev": ev,
                "p": _period(r.get("Period")),
                "svy": fmt(r.get("Survey")),
                "act": fmt(r.get("Actual")),
                "pri": fmt(r.get("Prior")),
                "rev": fmt(r.get("Revised")),
                "rel": round(rel, 1),
                "kind": kind,
            })
            kept += 1
        stat.append((p, kind, len(df), kept, dropped, skipped, dup, diag))

    rows.sort(key=lambda x: (x["d"], x["t"], -x["rel"]))

    if verbose:
        label = {"ind": "지표", "evt": "연설·이벤트"}
        print("[source] " + BASE)
        for p, kind, total, kept, dropped, skipped, dup, diag in stat:
            mt = dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
            tail = ", 컨센서스 없어 제외 {}행".format(dropped) if dropped else ""
            tail += ", 최신 파일에 있어 건너뜀 {}행".format(dup) if dup else ""
            tail += ", 빈줄·꼬리 {}행".format(skipped) if skipped else ""
            print("  * {}  (수정 {})  -> {}({})  {}행 중 {}행 사용{}".format(
                os.path.basename(p), mt, label[kind], kind, total, kept, tail))
            print("      판별근거: " + diag)
        print("[rows] {}".format(len(rows)))
    return rows


def main():
    rows = load_rows(verbose=True)
    if not rows:
        print("행이 없습니다 — 엑셀 내용을 확인하세요")
        return
    ind = [r for r in rows if r["kind"] == "ind"]
    evt = [r for r in rows if r["kind"] == "evt"]
    ccs = {}
    for r in rows:
        ccs[r["cc"]] = ccs.get(r["cc"], 0) + 1
    print("[kind] 지표 {} / 연설·이벤트 {}".format(len(ind), len(evt)))
    print("[기간] {} ~ {}".format(rows[0]["d"], rows[-1]["d"]))
    print("[국가] " + ", ".join("{} {}".format(k, v)
                              for k, v in sorted(ccs.items(), key=lambda kv: -kv[1])))
    print("[샘플]")
    for r in rows[:5] + rows[-3:]:
        print("  {} {:>5} {} {:<3} {:<3} {:<42} svy={:<9} act={:<9} pri={:<9} rel={}".format(
            r["d"], r["t"], r["flag"], r["cc"], r["kind"], r["ev"][:42],
            r["svy"], r["act"], r["pri"], r["rel"]))


if __name__ == "__main__":
    main()
