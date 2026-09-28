# -*- coding: utf-8 -*-
r"""
rawdata.py — 원본 엑셀을 한 곳(`____Rawdata___`)에서 찾아주는 공용 헬퍼
=====================================================================
받은 엑셀을 파이프라인별 폴더에 나눠 넣지 않고 `QAE\____Rawdata___\` 한 곳에
떨궈 넣으면, 각 스크립트가 여기서 자기 파일을 집어간다.

찾는 방법은 **파일명 앞부분(prefix)** 하나뿐이다. 뒤에 뭐가 붙어도 상관없다.

    ECFC_Growth Consesus_수정.xlsb
    ECFC_Growth Consesus_수정 (2).xlsb      <- 브라우저가 붙인 (2)
    ECFC_Growth Consesus_수정_20260909.xlsb
    ^^^^^^^^^^^^^^^^^^^^ 여기까지만 맞으면 전부 같은 파일로 본다

같은 prefix 가 여러 개면 **수정시각이 가장 최근인 것** 하나를 쓴다.
(같으면 파일명 역순 — `(2)` 가 `(1)` 보다 먼저)

쓰는 쪽:
    import rawdata
    p = rawdata.find("ECFC_Growth Consesus", exts=(".xlsb",),
                     extra_dirs=[BASE_DIR])      # 없으면 기존 폴더로 폴백
    files = rawdata.find_all("Bquant_", exts=(".xlsb", ".xlsx"))

폴더 위치를 옮기려면 환경변수 `QAE_RAWDATA_DIR` 로 덮어쓴다.

점검:
    python rawdata.py        # 폴더에 뭐가 있고 어느 파이프라인이 집어가는지 출력
"""

import os
import sys

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.environ.get("QAE_RAWDATA_DIR") or os.path.join(REPO_DIR, "____Rawdata___")

# 어떤 prefix 를 어느 파이프라인이 집어가는지 — 점검 출력과 문서용.
# (실제 매칭은 각 스크립트가 자기 prefix 로 직접 호출한다)
KNOWN = [
    (("ECFC_Growth_Consensus", "ECFC_Growth Consesus"), (".xlsb",), "Consensus Builder — GDP 컨센서스"),
    (("ECFC_Inflation_Consensus", "ECFC_Inflation Consesus"), (".xlsb",), "Consensus Builder — CPI 컨센서스"),
    (("Bquant_",),             (".xlsb", ".xlsx"),  "데일리시황 BQL — BQuant_Master"),
    (("",),                    (".xlsx",),          "블벅경제지표 — WECO/BQuant 캘린더 (내용으로 판별)"),
]


def _candidates(directory, exts):
    """directory 안에서 확장자가 맞는 파일 경로 목록. 엑셀 임시파일(~$)은 뺀다."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    exts = tuple(e.lower() for e in exts)
    out = []
    for name in names:
        if name.startswith("~$"):
            continue
        if not name.lower().endswith(exts):
            continue
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            out.append(path)
    return out


def search_dirs(extra_dirs=()):
    """실제로 존재하는 검색 폴더 목록. `____Rawdata___` 가 항상 먼저다."""
    dirs = [RAW_DIR] + [d for d in extra_dirs if d]
    seen, out = set(), []
    for d in dirs:
        key = os.path.normcase(os.path.abspath(d))
        if key in seen or not os.path.isdir(d):
            continue
        seen.add(key)
        out.append(d)
    return out


def find_all(prefix, exts=(".xlsx", ".xlsb"), extra_dirs=()):
    """prefix 로 시작하는 파일을 **최신순**으로 전부. 대소문자는 안 가린다.

    `____Rawdata___` 를 먼저 보고, extra_dirs(보통 기존 입력 폴더)를 그 다음에 본다.
    정렬은 폴더와 무관하게 수정시각 기준이라, 예전 폴더에 더 새 파일이 있으면
    그쪽이 먼저 나온다.
    """
    key = prefix.lower()
    hits = []
    for d in search_dirs(extra_dirs):
        for path in _candidates(d, exts):
            if os.path.basename(path).lower().startswith(key):
                hits.append(path)
    hits.sort(key=lambda p: (os.path.getmtime(p), os.path.basename(p)), reverse=True)
    return hits


def find(prefix, exts=(".xlsx", ".xlsb"), extra_dirs=()):
    """`find_all` 의 첫 번째. 없으면 None."""
    hits = find_all(prefix, exts, extra_dirs)
    return hits[0] if hits else None


def find_any(prefixes, exts=(".xlsx", ".xlsb"), extra_dirs=()):
    """여러 허용 prefix 중 수정시각이 가장 최근인 파일 하나."""
    hits = []
    for prefix in prefixes:
        hits.extend(find_all(prefix, exts, extra_dirs))
    if not hits:
        return None
    hits = list(dict.fromkeys(hits))
    hits.sort(key=lambda p: (os.path.getmtime(p), os.path.basename(p)), reverse=True)
    return hits[0]


def require(prefix, exts=(".xlsx", ".xlsb"), extra_dirs=()):
    """없으면 FileNotFoundError. 어디를 뒤졌는지 메시지에 담는다."""
    hit = find(prefix, exts, extra_dirs)
    if hit:
        return hit
    looked = " / ".join(search_dirs(extra_dirs)) or RAW_DIR
    raise FileNotFoundError(
        "'{}*{}' 파일을 못 찾았습니다. 넣을 곳: {}".format(
            prefix, "|".join(exts), looked))


def require_any(prefixes, exts=(".xlsx", ".xlsb"), extra_dirs=()):
    """여러 허용 prefix 중 하나도 없으면 FileNotFoundError."""
    hit = find_any(prefixes, exts, extra_dirs)
    if hit:
        return hit
    looked = " / ".join(search_dirs(extra_dirs)) or RAW_DIR
    raise FileNotFoundError(
        "'{}*{}' 파일을 못 찾았습니다. 넣을 곳: {}".format(
            " 또는 ".join(prefixes), "|".join(exts), looked))


def describe(prefix, exts=(".xlsx", ".xlsb"), extra_dirs=()):
    """로그 한 줄용: '경로 (2026-09-09 17:32)'."""
    import datetime as _dt
    hit = find(prefix, exts, extra_dirs)
    if not hit:
        return "(없음)"
    ts = _dt.datetime.fromtimestamp(os.path.getmtime(hit))
    return "{} ({:%Y-%m-%d %H:%M})".format(hit, ts)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("[rawdata] 폴더: " + RAW_DIR)
    if not os.path.isdir(RAW_DIR):
        print("  !! 폴더가 없습니다. 만들어서 엑셀을 넣으세요.")
        return 1
    files = _candidates(RAW_DIR, (".xlsx", ".xlsb", ".xls", ".csv"))
    if not files:
        print("  (비어 있음)")
    for p in sorted(files, key=os.path.getmtime, reverse=True):
        import datetime as _dt
        ts = _dt.datetime.fromtimestamp(os.path.getmtime(p))
        print("  - {:<55} {:%Y-%m-%d %H:%M}  {:>9,}B".format(
            os.path.basename(p), ts, os.path.getsize(p)))
    print("\n[매칭] prefix -> 집어가는 곳")
    for prefixes, exts, who in KNOWN:
        hit = find_any(prefixes, exts)
        mark = os.path.basename(hit) if hit else "(없음)"
        label = " / ".join(prefixes) if any(prefixes) else "(모든 xlsx)"
        print("  {:<26} {:<40} {}".format(label, mark, who))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
