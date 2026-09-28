from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


HERE = Path(__file__).resolve().parent
DEFAULT_BQL_ROOT = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\BQL")
DEFAULT_OUTPUT_ROOT = DEFAULT_BQL_ROOT / "Theme" / "output"
DEFAULT_BOOK = DEFAULT_BQL_ROOT / "Theme" / "Material" / "Sector_Industry" / "stock_descriptions.xlsx"

SECTOR_KO = {
    "Communication Services": "커뮤니케이션 서비스",
    "Consumer Discretionary": "경기소비재",
    "Consumer Staples": "필수소비재",
    "Energy": "에너지",
    "Financials": "금융",
    "Health Care": "헬스케어",
    "Industrials": "산업재",
    "Information Technology": "정보기술",
    "Materials": "소재",
    "Real Estate": "부동산",
    "Utilities": "유틸리티",
}

INDUSTRY_KO = {
    "Automobiles & Components": "자동차 및 자동차부품",
    "Banks": "은행",
    "Capital Goods": "자본재·기계·산업장비",
    "Commercial & Professional Services": "상업·전문 서비스",
    "Communication Services": "통신 서비스",
    "Consumer Discretionary Distribution & Retail": "경기소비재 유통·소매",
    "Consumer Durables & Apparel": "내구소비재·의류",
    "Consumer Services": "소비자 서비스",
    "Consumer Staples Distribution & Retail": "필수소비재 유통·소매",
    "Energy": "석유·가스 및 에너지",
    "Equity Real Estate Investment Trusts (REITs)": "상장 부동산·리츠",
    "Financial Services": "금융 서비스",
    "Food, Beverage & Tobacco": "식품·음료·담배",
    "Health Care Equipment & Services": "의료기기·헬스케어 서비스",
    "Household & Personal Products": "생활용품·개인용품",
    "Insurance": "보험",
    "Materials": "화학·금속·건자재 등 소재",
    "Media & Entertainment": "미디어·엔터테인먼트",
    "Pharmaceuticals, Biotechnology & Life Sciences": "제약·바이오·생명과학",
    "Real Estate Management & Development": "부동산 관리·개발",
    "Semiconductors & Semiconductor Equipment": "반도체·반도체 장비",
    "Software & Services": "소프트웨어·IT 서비스",
    "Technology Hardware & Equipment": "기술 하드웨어·전자장비",
    "Transportation": "운송·물류",
    "Utilities": "전력·가스·수도 유틸리티",
}

HEADERS = [
    "Market",
    "Ticker",
    "Company Name",
    "GICS Sector",
    "GICS Industry Group",
    "Business Summary (KR)",
    "Web Profile",
    "Source URL",
    "Verified Date",
    "Status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an editable stock-description workbook for current report names.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--web", action="store_true", help="Enrich identity and profile from Wikidata.")
    parser.add_argument("--refresh-web", action="store_true", help="Re-query existing rows as well as missing rows.")
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def latest_data_files(output_root: Path) -> list[Path]:
    candidates = sorted(output_root.glob("*/Sector_Industry/글로벌_섹터_산업_*_데이터_*.json"))
    if not candidates:
        raise FileNotFoundError(f"통합 섹터 JSON이 없습니다: {output_root}")
    latest_tag = max(path.parent.parent.name for path in candidates)
    return [path for path in candidates if path.parent.parent.name == latest_tag]


def collect_selected(files: list[Path]) -> list[dict[str, str]]:
    selected: dict[tuple[str, str], dict[str, str]] = {}
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for market in payload["markets"]:
            stock = market["stock"]
            for sector in market["sectors"]:
                for idx in list(sector["top"]) + list(sector["bottom"]):
                    key = (market["key"], stock["ticker"][idx])
                    selected[key] = {
                        "Market": market["key"],
                        "Ticker": stock["ticker"][idx],
                        "Company Name": stock["name"][idx],
                        "GICS Sector": stock["sector"][idx],
                        "GICS Industry Group": stock["industry"][idx],
                    }
    return sorted(selected.values(), key=lambda row: (row["Market"], row["GICS Sector"], row["Company Name"]))


def load_existing(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if "Stock_Descriptions" not in workbook.sheetnames:
            return {}
        ws = workbook["Stock_Descriptions"]
        headers = [str(cell.value or "").strip() for cell in ws[1]]
        columns = {value: idx for idx, value in enumerate(headers)}
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            market = str(values[columns.get("Market", 0)] or "").strip()
            ticker = str(values[columns.get("Ticker", 1)] or "").strip()
            if not market or not ticker:
                continue
            result[(market, ticker)] = {
                header: values[columns[header]] if header in columns and columns[header] < len(values) else None
                for header in HEADERS
            }
        return result
    finally:
        workbook.close()


def normalized_name(value: str) -> str:
    text = value.lower().replace("/the", " ")
    text = re.sub(r"\b(the|inc|corp|corporation|co|company|plc|sa|ag|nv|se|ltd|limited|holdings?|group)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def score_candidate(company: str, candidate: dict[str, Any]) -> float:
    source = normalized_name(company)
    labels = [candidate.get("label", "")] + list(candidate.get("aliases", []) or [])
    similarities = [SequenceMatcher(None, source, normalized_name(label)).ratio() for label in labels if label]
    score = max(similarities or [0.0])
    description = str(candidate.get("description", "")).lower()
    if any(word in description for word in ("company", "manufacturer", "bank", "corporation", "retailer", "airline", "business")):
        score += 0.12
    return score


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "NPS-BQL-Sector-Report/1.0"})
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.load(response)


def search_wikidata(row: dict[str, str]) -> dict[str, str]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": row["Company Name"],
            "format": "json",
            "srlimit": 5,
        }
    )
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    try:
        results = fetch_json(url).get("query", {}).get("search", [])
        if not results:
            return {"Web Profile": "", "Source URL": "", "Status": "GICS fallback"}
        candidates = [
            {
                "label": item.get("title", ""),
                "description": re.sub(r"<[^>]+>", "", str(item.get("snippet", ""))),
                "raw": item,
            }
            for item in results
        ]
        best = max(candidates, key=lambda item: score_candidate(row["Company Name"], item))
        if score_candidate(row["Company Name"], best) < 0.40:
            return {"Web Profile": "", "Source URL": "", "Status": "GICS fallback"}
        title = str(best["raw"].get("title") or "").strip()
        return {
            "Web Profile": str(best.get("description") or "").strip(),
            "Source URL": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "Status": "Web matched (Wikipedia)",
        }
    except Exception as error:
        return {"Web Profile": "", "Source URL": "", "Status": f"Web error: {type(error).__name__}"}


def resolve_title(title: str, normalized: dict[str, str], redirects: dict[str, str]) -> str:
    current = title
    for _ in range(5):
        updated = normalized.get(current, redirects.get(current, current))
        if updated == current:
            break
        current = updated
    return current


def wikipedia_title(company_name: str) -> str:
    title = company_name.replace("/The", "").strip()
    suffix = re.compile(
        r"(?:,?\s+(?:Inc|Corp|Corporation|Co|Company|PLC|SA|AG|NV|SE|Ltd|Limited|Holdings|Group))\.?$",
        re.IGNORECASE,
    )
    previous = None
    while title and title != previous:
        previous = title
        title = suffix.sub("", title).strip()
    return title or company_name


def fetch_wikipedia_batches(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    profiles: dict[tuple[str, str], dict[str, str]] = {}
    batch_size = 40
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        requested = {wikipedia_title(row["Company Name"]): row for row in batch}
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "redirects": 1,
                "titles": "|".join(requested),
                "format": "json",
            }
        )
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        try:
            query = fetch_json(url).get("query", {})
            normalized = {item["from"]: item["to"] for item in query.get("normalized", [])}
            redirects = {item["from"]: item["to"] for item in query.get("redirects", [])}
            pages = {
                str(page.get("title") or ""): page
                for page in query.get("pages", {}).values()
                if "missing" not in page
            }
            pages_lower = {title.lower(): page for title, page in pages.items()}
            for title, row in requested.items():
                final_title = resolve_title(title, normalized, redirects)
                page = pages.get(final_title) or pages_lower.get(final_title.lower())
                key = (row["Market"], row["Ticker"])
                extract = str((page or {}).get("extract") or "").strip()
                if page and extract:
                    profile = extract.split("\n", 1)[0].strip()
                    profiles[key] = {
                        "Web Profile": profile[:600],
                        "Source URL": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(str(page["title"]).replace(" ", "_")),
                        "Status": "Web matched (Wikipedia batch)",
                    }
                else:
                    profiles[key] = {"Web Profile": "", "Source URL": "", "Status": "GICS fallback"}
        except Exception as error:
            for row in batch:
                profiles[(row["Market"], row["Ticker"])] = {
                    "Web Profile": "",
                    "Source URL": "",
                    "Status": f"Web error: {type(error).__name__}",
                }
        print(f"web_progress={min(start + batch_size, len(rows))}/{len(rows)}", flush=True)
        time.sleep(0.25)
    return profiles


def business_summary(row: dict[str, str], web_profile: str) -> str:
    sector = SECTOR_KO.get(row["GICS Sector"], row["GICS Sector"])
    industry = INDUSTRY_KO.get(row["GICS Industry Group"], row["GICS Industry Group"])
    line1 = f"{row['Company Name']}은(는) {industry} 분야를 중심으로 사업을 영위하는 {sector} 기업이다."
    if web_profile:
        line2 = f"공개 기업 프로필은 ‘{web_profile}’로 소개하며, 세부 사업 분류는 {row['GICS Industry Group']}이다."
    else:
        line2 = f"주요 사업 분류는 {row['GICS Industry Group']}이다."
    return line1 + "\n" + line2


def build_rows(selected: list[dict[str, str]], existing: dict[tuple[str, str], dict[str, Any]], use_web: bool, refresh_web: bool, workers: int) -> list[dict[str, Any]]:
    profiles: dict[tuple[str, str], dict[str, str]] = {}
    targets = []
    for row in selected:
        key = (row["Market"], row["Ticker"])
        old = existing.get(key, {})
        if use_web and (refresh_web or not old.get("Source URL")):
            targets.append(row)
        else:
            profiles[key] = {
                "Web Profile": str(old.get("Web Profile") or ""),
                "Source URL": str(old.get("Source URL") or ""),
                "Status": str(old.get("Status") or "GICS fallback"),
            }

    if targets:
        profiles.update(fetch_wikipedia_batches(targets))

    output: list[dict[str, Any]] = []
    today = date.today().isoformat()
    for row in selected:
        key = (row["Market"], row["Ticker"])
        old = existing.get(key, {})
        profile = profiles[key]
        summary = str(old.get("Business Summary (KR)") or "").strip()
        if not summary or (profile["Web Profile"] and "필요하면 이 Excel" in summary):
            summary = business_summary(row, profile["Web Profile"])
        output.append(
            {
                **row,
                "Business Summary (KR)": summary,
                "Web Profile": profile["Web Profile"],
                "Source URL": profile["Source URL"],
                "Verified Date": today if use_web and profile["Source URL"] else str(old.get("Verified Date") or ""),
                "Status": profile["Status"],
            }
        )
    return output


def write_workbook(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    readme = workbook.active
    readme.title = "README"
    readme.column_dimensions["A"].width = 24
    readme.column_dimensions["B"].width = 105
    instructions = [
        ("목적", "통합 섹터 HTML의 상승·하락 종목 아래에 표시할 2줄 사업 설명 마스터"),
        ("수정 열", "Stock_Descriptions 시트의 Business Summary (KR)를 직접 수정하면 다음 HTML 생성부터 반영"),
        ("조회 키", "Market + Ticker 조합"),
        ("자동 범위", "최신 1D·5D 보고서에 등장하는 상·하위 종목의 합집합"),
        ("출처", "Wikidata 공개 기업 검색 결과. GICS Sector/Industry Group은 BQuant Master"),
        ("주의", "Web matched는 이름 유사도 기반 자동 연결이므로 중요한 종목은 Source URL을 열어 확인"),
        ("예시", "SP500 | ADBE UW Equity | Adobe Inc | 소프트웨어·IT 서비스 회사 …"),
    ]
    for row_idx, (label, value) in enumerate(instructions, 1):
        readme.cell(row_idx, 1, label).font = Font(name="Arial", bold=True, color="FFFFFF")
        readme.cell(row_idx, 1).fill = PatternFill("solid", fgColor="17365D")
        readme.cell(row_idx, 2, value).font = Font(name="Arial", size=10)
        readme.cell(row_idx, 2).alignment = Alignment(wrap_text=True, vertical="top")

    ws = workbook.create_sheet("Stock_Descriptions")
    ws.append(HEADERS)
    for row in rows:
        ws.append([row.get(header, "") for header in HEADERS])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:J{ws.max_row}"
    widths = {"A": 12, "B": 22, "C": 34, "D": 24, "E": 48, "F": 92, "G": 48, "H": 34, "I": 14, "J": 18}
    for column, width in widths.items():
        ws.column_dimensions[column].width = width
    for cell in ws[1]:
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17365D")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial", size=9)
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (6, 7, 8))
        row[5].font = Font(name="Arial", size=9, color="0000FF")
        ws.row_dimensions[row[0].row].height = 36
    if ws.max_row >= 2:
        table = Table(displayName="StockDescriptions", ref=f"A1:J{ws.max_row}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showFirstColumn=False, showLastColumn=False)
        ws.add_table(table)
    workbook.save(path)


def main() -> None:
    args = parse_args()
    files = latest_data_files(args.output_root.resolve())
    selected = collect_selected(files)
    existing = load_existing(args.output.resolve())
    rows = build_rows(selected, existing, args.web, args.refresh_web, args.workers)
    write_workbook(args.output.resolve(), rows)
    print(f"rows={len(rows)}")
    print(f"output={args.output.resolve()}")


if __name__ == "__main__":
    main()
