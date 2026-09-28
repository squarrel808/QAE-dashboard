from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
MATERIAL_DIR = SCRIPT_DIR.parent
THEME_DIR = MATERIAL_DIR.parent
BQL_DIR = THEME_DIR.parent
DEFAULT_MASTER = BQL_DIR / "Rawfile" / "BQuant_Master.xlsx"
sys.path.insert(0, str(BQL_DIR / "Dashbaord"))
import build_regional_dashboards as raw_builder  # noqa: E402


STAGES = [
    {
        "key": "hyperscale",
        "name": "하이퍼스케일러·플랫폼",
        "short": "하이퍼스케일러",
        "color": "#ea580c",
        "description": "대규모 AI 클라우드, 기반모델 유통, 데이터 플랫폼과 기업용 AI 배포 채널.",
        "core": "MSFT AMZN GOOGL META ORCL".split(),
        "adjacent": "IBM".split(),
    },
    {
        "key": "compute",
        "name": "AI 연산·메모리",
        "short": "연산·메모리",
        "color": "#2563eb",
        "description": "AI 가속기, CPU, HBM·메모리, 맞춤형 AI 반도체와 전력관리 반도체.",
        "core": "NVDA AMD AVGO MRVL MU".split(),
        "adjacent": "INTC MPWR".split(),
    },
    {
        "key": "semicap",
        "name": "파운드리·반도체 장비·EDA",
        "short": "반도체 장비·EDA",
        "color": "#7c3aed",
        "description": "선단공정 증설에 필요한 웨이퍼 장비, 공정제어, 테스트, 첨단패키징과 칩 설계 소프트웨어.",
        "core": "AMAT LRCX KLAC CDNS SNPS TER".split(),
        "adjacent": "".split(),
    },
    {
        "key": "network",
        "name": "네트워크·광통신",
        "short": "네트워크·광통신",
        "color": "#0891b2",
        "description": "AI 클러스터의 스케일업·스케일아웃을 연결하는 이더넷, 스위치, 광부품, 케이블과 인터커넥트.",
        "core": "ANET CSCO CIEN COHR".split(),
        "adjacent": "LITE GLW APH".split(),
    },
    {
        "key": "server",
        "name": "서버·스토리지",
        "short": "서버·스토리지",
        "color": "#0284c7",
        "description": "AI 서버, 랙 통합, 위탁생산, 기업·클라우드 스토리지와 데이터 관리.",
        "core": "DELL HPE SMCI".split(),
        "adjacent": "FLEX JBL NTAP STX WDC SNDK".split(),
    },
    {
        "key": "power_equipment",
        "name": "전력·냉각 장비",
        "short": "전력·냉각 장비",
        "color": "#0f766e",
        "description": "데이터센터 전력배전, 스위치기어, UPS, 열관리, 냉각과 전력망 장비.",
        "core": "VRT ETN GEV".split(),
        "adjacent": "HUBB TT JCI CARR".split(),
    },
    {
        "key": "construction",
        "name": "E&C·설계·전기공사",
        "short": "E&C·전기공사",
        "color": "#b45309",
        "description": "데이터센터와 전력망의 설계·시공, 전기·기계 공사와 연결 인프라 구축.",
        "core": "PWR".split(),
        "adjacent": "FIX EME".split(),
    },
    {
        "key": "generation",
        "name": "전력 생산",
        "short": "전력 생산",
        "color": "#16a34a",
        "description": "데이터센터 전력수요 증가와 장기 전력계약에 직접 노출된 발전사업자.",
        "core": "CEG VST".split(),
        "adjacent": "NRG".split(),
    },
    {
        "key": "dc_reit",
        "name": "데이터센터 REIT·운영사",
        "short": "데이터센터 REIT",
        "color": "#64748b",
        "description": "코로케이션, 상호접속과 데이터센터 부동산을 소유·운영하는 플랫폼.",
        "core": "DLR EQIX".split(),
        "adjacent": "IRM".split(),
    },
    {
        "key": "cyber",
        "name": "사이버보안",
        "short": "사이버보안",
        "color": "#dc2626",
        "description": "AI 워크로드, 클라우드, 엔드포인트와 네트워크를 보호하는 보안 플랫폼.",
        "core": "CRWD PANW FTNT".split(),
        "adjacent": "AKAM GEN".split(),
    },
    {
        "key": "software",
        "name": "AI 소프트웨어·데이터",
        "short": "AI 소프트웨어·데이터",
        "color": "#db2777",
        "description": "기업 워크플로, 데이터 분석, 창작, 관측성과 애플리케이션 계층의 AI 수익화.",
        "core": "PLTR NOW CRM ADBE APP".split(),
        "adjacent": "INTU WDAY DDOG ACN".split(),
    },
    {
        "key": "edge",
        "name": "엣지·Physical AI",
        "short": "엣지·Physical AI",
        "color": "#65a30d",
        "description": "온디바이스 AI, 자율주행, 로봇, 산업용 센싱과 제어 등 데이터센터 밖의 AI.",
        "core": "QCOM TSLA AXON".split(),
        "adjacent": "AAPL NXPI ADI ON ROK".split(),
    },
]


RATIONALES = {
    "MSFT": "Azure AI 인프라, 모델, Copilot과 기업 고객 유통망을 동시에 보유.",
    "AMZN": "AWS AI 인프라, Trainium·Inferentia와 모델 서비스를 제공.",
    "GOOGL": "Google Cloud, Gemini와 TPU를 보유하며 GOOG는 이중가중 방지를 위해 제외.",
    "META": "대규모 AI 인프라, 오픈모델과 광고·추천 수익화를 결합.",
    "ORCL": "OCI의 대형 AI 학습 클러스터와 데이터베이스 고객 기반을 보유.",
    "IBM": "하이브리드 클라우드, watsonx와 AI 컨설팅 노출은 있으나 순수도는 낮음.",
    "NVDA": "AI 가속기, 네트워크와 소프트웨어를 결합한 풀스택 플랫폼.",
    "AMD": "데이터센터 CPU와 AI 가속기 사업을 보유.",
    "AVGO": "맞춤형 AI 가속기와 스위칭·연결 반도체에 동시 노출.",
    "MRVL": "맞춤형 AI 실리콘, 전기광학과 데이터센터 네트워크 반도체 공급.",
    "MU": "HBM과 데이터센터 DRAM·NAND 수요에 직접 노출.",
    "INTC": "CPU, 파운드리와 가속기 노출이 있으나 AI 이익 기여 집중도는 낮음.",
    "MPWR": "고성능 컴퓨팅 시스템용 전력관리 반도체 공급.",
    "AMAT": "폭넓은 웨이퍼 장비와 첨단패키징 노출.",
    "LRCX": "선단 로직·메모리와 HBM 증설에 필요한 식각·증착 장비 공급.",
    "KLAC": "반도체 복잡도 상승에 필요한 공정제어·검사 장비 공급.",
    "CDNS": "첨단 AI 반도체 설계를 위한 EDA와 시스템 설계 소프트웨어 제공.",
    "SNPS": "AI 실리콘 설계에 사용되는 EDA와 반도체 IP 제공.",
    "TER": "AI 가속기와 첨단 반도체용 테스트 장비 공급.",
    "ANET": "AI 패브릭용 고속 이더넷 스위칭의 직접 수혜.",
    "CSCO": "AI 데이터센터 패브릭용 네트워크·광학·보안 솔루션 제공.",
    "CIEN": "데이터센터 인터커넥트와 AI 트래픽 증가에 필요한 광네트워크 공급.",
    "COHR": "고속 AI 인터커넥트용 광부품과 트랜시버 공급.",
    "LITE": "클라우드·데이터센터 연결에 사용되는 광부품 공급.",
    "GLW": "데이터센터 증설에 필요한 광섬유와 연결 제품 공급.",
    "APH": "데이터센터 시스템용 고속 커넥터와 케이블 공급.",
    "DELL": "기업용 AI 서버, 랙과 스토리지 시스템 공급.",
    "HPE": "AI 시스템과 Aruba 네트워크를 결합한 기업 인프라 공급.",
    "SMCI": "고밀도 AI 서버와 랙스케일 통합의 직접 수혜.",
    "FLEX": "데이터센터 하드웨어 설계·위탁생산 노출.",
    "JBL": "클라우드 고객 대상 제조와 데이터센터 인프라 하드웨어 노출.",
    "NTAP": "AI 워크로드용 기업 스토리지와 데이터 관리 제공.",
    "STX": "클라우드와 AI 데이터 파이프라인용 대용량 스토리지 공급.",
    "WDC": "기업·클라우드 스토리지 수요에 노출.",
    "SNDK": "데이터 집약적 워크로드용 플래시 스토리지 노출.",
    "VRT": "고밀도 AI 데이터센터의 전력·열관리·액체냉각 인프라 공급.",
    "ETN": "데이터센터 부하 증가에 필요한 배전·스위치기어·전력품질 장비 공급.",
    "GEV": "전력망 장비와 발전설비를 통해 데이터센터 전력수요에 노출.",
    "HUBB": "전력망 보강용 유틸리티·전기 부품 공급.",
    "TT": "고효율 냉각·열관리 시스템에 노출되지만 AI 순수도는 낮음.",
    "JCI": "데이터센터 빌딩제어와 냉각 인프라 공급.",
    "CARR": "데이터센터 증설에 필요한 HVAC와 열관리 노출.",
    "PWR": "신규 발전과 데이터센터를 연결하는 전력망·전기 인프라 시공.",
    "FIX": "데이터센터 냉각 프로젝트를 포함한 기계·전기 공사 수행.",
    "EME": "데이터센터 프로젝트에 필요한 전기·기계 시공 노출.",
    "CEG": "하이퍼스케일 데이터센터용 원전·청정전력 장기계약의 직접 수혜.",
    "VST": "경쟁 발전과 데이터센터 전력계약에 노출.",
    "NRG": "데이터센터 부하 증가에 레버리지된 발전·소매전력 사업.",
    "DLR": "글로벌 데이터센터 REIT와 코로케이션 플랫폼.",
    "EQIX": "상호접속 중심의 글로벌 데이터센터 운영 플랫폼.",
    "IRM": "데이터센터를 운영하지만 기록관리 사업 비중이 더 커 순수도는 낮음.",
    "CRWD": "AI 기반 엔드포인트·클라우드 보안 플랫폼.",
    "PANW": "AI 기반 사이버보안 플랫폼과 AI 워크로드 보호 솔루션 제공.",
    "FTNT": "네트워크·클라우드 보안과 AI 기반 위협탐지 플랫폼 제공.",
    "AKAM": "클라우드 보안과 엣지 네트워크에 노출되지만 AI 순수도는 낮음.",
    "GEN": "소비자 사이버보안 사업으로 AI 보안 수요에 간접 노출.",
    "PLTR": "민간·정부 워크플로에 AI 플랫폼과 애플리케이션을 배포.",
    "NOW": "기업 워크플로 자동화와 생성형 AI 제품을 수익화.",
    "CRM": "에이전틱 AI와 기업 고객데이터 유통망을 결합.",
    "ADBE": "생성형 창작도구와 문서 AI를 수익화.",
    "APP": "AI 기반 광고 최적화와 소프트웨어 플랫폼 운영.",
    "INTU": "금융·세무 워크플로에 AI 어시스턴트를 내장.",
    "WDAY": "인사·재무 워크플로에 AI 기능을 내장.",
    "DDOG": "복잡한 클라우드·AI 애플리케이션 스택의 관측성 제공.",
    "ACN": "고객사의 AI 구축·컨설팅 지출에 간접 노출.",
    "QCOM": "온디바이스 AI 가속기와 엣지 연결 반도체 공급.",
    "TSLA": "자율주행, 추론 하드웨어와 로봇·Physical AI 개발.",
    "AXON": "AI 기반 공공안전 장비와 증거·업무 소프트웨어 제공.",
    "AAPL": "대규모 설치기반의 온디바이스 AI 노출은 있으나 기기 사이클 의존도가 높음.",
    "NXPI": "자동차·산업용 엣지 프로세서 공급.",
    "ADI": "엣지 지능을 위한 산업용 센싱과 신호처리 반도체 공급.",
    "ON": "자동차·산업용 센싱과 전력반도체 공급.",
    "ROK": "Physical AI를 가능하게 하는 산업 자동화·제어 시스템 공급.",
}


SOURCES = [
    ["IEA — Energy and AI", "https://www.iea.org/reports/energy-and-ai", "데이터센터 전력수요와 전력시스템 분석 체계."],
    ["IEA — 2026 data-centre electricity update", "https://www.iea.org/news/data-centre-electricity-use-surged-in-2025-even-with-tightening-bottlenecks-driving-a-scramble-for-solutions", "데이터센터 전력수요 가속과 인프라 병목."],
    ["McKinsey — infrastructure that powers and cools AI data centers", "https://www.mckinsey.com/industries/industrials/our-insights/beyond-compute-infrastructure-that-powers-and-cools-ai-data-centers", "전력·냉각·물리 인프라 분류 근거."],
    ["McKinsey — AI hardware opportunities", "https://www.mckinsey.com/industries/semiconductors/our-insights/artificial-intelligence-hardware-new-opportunities-for-semiconductor-companies/pl-PL", "연산·메모리·네트워크·스토리지 공급망 구분."],
    ["NVIDIA FY2026 results", "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2026/", "가속컴퓨팅 수요와 데이터센터 매출."],
    ["AMD 2025 Form 10-K", "https://ir.amd.com/financial-information/sec-filings/content/0000002488-26-000018/amd-20251227.htm", "CPU·GPU와 데이터센터 사업 노출."],
    ["Broadcom Q2 FY2026 results", "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-second-quarter-fiscal-year-2026-financial", "맞춤형 AI 실리콘과 네트워크 노출."],
    ["Arista Q2 2026 results", "https://investors.arista.com/Communications/Press-Releases-and-Events/Press-Release-Detail/2026/Arista-Networks-Inc--Reports-Second-Quarter-2026-Financial-Results/default.aspx", "AI 네트워크와 이더넷 패브릭 수요."],
    ["Vertiv FY2025 results", "https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-Fourth-Quarter-with-Organic-Orders-Growth-of-252-and-Diluted-EPS-Growth-of-200-Adjusted-Diluted-EPS-37/default.aspx", "데이터센터 전력·열관리 수요."],
    ["Eaton Q1 2026 results", "https://www.eaton.com/us/en-us/company/news-insights/news-releases/2026/eaton-reports-record-first-quarter-2026-results.html", "북미 전기장비 주문과 데이터센터 모멘텀."],
    ["Microsoft FY2026 Q4 earnings", "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4", "Azure AI 용량과 클라우드 투자."],
    ["Alphabet 2025 Q4 earnings", "https://abc.xyz/investor/events/event-details/2026/2025-Q4-Earnings-Call-2026-Dr_C033hS6/default.aspx", "클라우드·AI 백로그와 설비투자."],
    ["Amazon Q2 2026 results", "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000024/amzn-20260630xex991.htm", "AWS와 자체 AI 반도체 노출."],
    ["Meta Q2 2026 Form 10-Q", "https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm", "AI 인프라 설비투자."],
]


def ticker_symbol(value: str) -> str:
    return value.split()[0].strip().upper()


def load_spx(sources: list[Path] | None = None) -> raw_builder.RawIndex:
    selected: raw_builder.RawIndex | None = None
    selected_sources = sources or [DEFAULT_MASTER]
    for source in selected_sources:
        if not source.exists():
            continue
        for raw in raw_builder.iter_raw_indices(source):
            if raw.code != "SPX":
                continue
            selected = raw if selected is None else raw_builder.merge_raw_indices(selected, raw)
    if selected is None:
        joined = ", ".join(str(source) for source in selected_sources)
        raise RuntimeError(f"SPX raw panel was not found in: {joined}")
    return selected


def valid_return(prices: np.ndarray, start: int, end: int) -> np.ndarray:
    before = prices[:, start]
    after = prices[:, end]
    valid = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
    out = np.full(len(before), np.nan)
    out[valid] = after[valid] / before[valid] - 1.0
    return out


def nearest_index(dates: list[date], target: date) -> int:
    candidates = [i for i, value in enumerate(dates) if value <= target]
    return candidates[-1] if candidates else 0


def latest_trading_index(prices: np.ndarray) -> int:
    """Ignore trailing holidays/stale copied rows and return the latest real SPX session."""
    for current in range(prices.shape[1] - 1, 0, -1):
        before = prices[:, current - 1]
        after = prices[:, current]
        valid = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
        if not valid.any():
            continue
        changed = ~np.isclose(after[valid], before[valid], rtol=1e-7, atol=1e-9)
        if float(changed.mean()) > 0.10:
            return current
    raise ValueError("SPX panel has no valid changing-price session")


def actual_session_indices(prices: np.ndarray) -> list[int]:
    """Return genuine market sessions, excluding holidays and carried rows."""
    sessions: list[int] = []
    for current in range(1, prices.shape[1]):
        before = prices[:, current - 1]
        after = prices[:, current]
        valid = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
        if not valid.any():
            continue
        changed = ~np.isclose(after[valid], before[valid], rtol=1e-7, atol=1e-9)
        if float(changed.mean()) > 0.10:
            sessions.append(current)
    return sessions


def shift_months(value: date, months: int) -> date:
    """Shift a date by whole calendar months, clamping the day if necessary."""
    month_index = value.year * 12 + value.month - 1 + months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    days = [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ]
    return date(year, month, min(value.day, days[month - 1]))


def reconcile_known_splits(prices: np.ndarray, tickers: list[str]) -> None:
    """Align known split-like source transitions without modifying the Master file."""
    symbol_to_row = {ticker_symbol(ticker): i for i, ticker in enumerate(tickers)}
    row = symbol_to_row.get("APH")
    if row is None:
        return
    series = prices[row]
    valid = np.flatnonzero(np.isfinite(series) & (series > 0))
    for left, right in zip(valid[:-1], valid[1:]):
        ratio = series[right] / series[left]
        if 1.8 <= ratio <= 2.2:
            series[right:] /= 2.0
    valid = np.flatnonzero(np.isfinite(series) & (series > 0))
    for left, right in zip(valid[:-1], valid[1:]):
        ratio = series[right] / series[left]
        if 0.45 <= ratio <= 0.55:
            series[:right] /= 2.0


def chain_series(
    prices: np.ndarray,
    market_caps: np.ndarray,
    members: list[int],
    dates: list[date],
) -> list[list[Any]]:
    """Rebase the shares-weighted aggregate Price to 100.

    Aggregate Price = sum(Price * Shares) / sum(Shares). The current source has
    no direct shares field, so Shares is reconstructed as Market Cap / Price.
    """
    level = 100.0
    result: list[list[Any]] = [[dates[0].isoformat(), level]]
    for current in range(1, len(dates)):
        previous = current - 1
        price0 = prices[members, previous]
        price1 = prices[members, current]
        mcap0 = market_caps[members, previous]
        mcap1 = market_caps[members, current]
        shares0 = np.divide(
            mcap0,
            price0,
            out=np.full_like(mcap0, np.nan, dtype=float),
            where=np.isfinite(mcap0) & np.isfinite(price0) & (mcap0 > 0) & (price0 > 0),
        )
        shares1 = np.divide(
            mcap1,
            price1,
            out=np.full_like(mcap1, np.nan, dtype=float),
            where=np.isfinite(mcap1) & np.isfinite(price1) & (mcap1 > 0) & (price1 > 0),
        )
        valid = (
            np.isfinite(price0) & np.isfinite(price1) &
            np.isfinite(shares0) & np.isfinite(shares1) &
            (price0 > 0) & (price1 > 0) & (shares0 > 0) & (shares1 > 0)
        )
        if valid.any():
            aggregate0 = float(np.average(price0[valid], weights=shares0[valid]))
            aggregate1 = float(np.average(price1[valid], weights=shares1[valid]))
            if aggregate0 > 0 and aggregate1 > 0:
                level *= aggregate1 / aggregate0
        result.append([dates[current].isoformat(), round(level, 6)])
    return result


def series_return(series: list[list[Any]], start: int, end: int) -> float | None:
    first = series[start][1]
    last = series[end][1]
    return round(last / first - 1.0, 6) if first and last else None


def period_indices(dates: list[date]) -> dict[str, int]:
    end = len(dates) - 1
    last = dates[end]
    return {
        "1D": max(0, end - 1),
        "5D": max(0, end - 5),
        "1W": nearest_index(dates, last - timedelta(days=7)),
        "1M": nearest_index(dates, shift_months(last, -1)),
        "3M": nearest_index(dates, shift_months(last, -3)),
        "6M": nearest_index(dates, shift_months(last, -6)),
        "YTD": nearest_index(dates, date(last.year, 1, 1)),
        "Since 2025-07-01": nearest_index(dates, date(2025, 7, 1)),
    }


def build_data(raw: raw_builder.RawIndex) -> dict[str, Any]:
    prices_all = raw.metrics["price"].copy()
    mcaps_all = raw.metrics["mcap"].copy()
    reconcile_known_splits(prices_all, raw.tickers)
    latest = latest_trading_index(prices_all)
    sessions = [idx for idx in actual_session_indices(prices_all) if idx <= latest]
    if len(sessions) < 2:
        raise ValueError("SPX panel has fewer than two genuine trading sessions")
    dates = [raw.dates[idx] for idx in sessions]
    prices = prices_all[:, sessions]
    mcaps = mcaps_all[:, sessions]
    symbol_to_row = {ticker_symbol(ticker): i for i, ticker in enumerate(raw.tickers)}
    periods = period_indices(dates)
    end = len(dates) - 1

    benchmark_members = list(range(len(raw.tickers)))
    benchmark_series = chain_series(prices, mcaps, benchmark_members, dates)
    benchmark_returns = {key: series_return(benchmark_series, start, end) for key, start in periods.items()}

    stocks: list[dict[str, Any]] = []
    stage_rows: dict[str, list[int]] = {}
    for stage in STAGES:
        rows: list[int] = []
        for confidence, symbols in (("Core", stage["core"]), ("Adjacent", stage["adjacent"])):
            for symbol in symbols:
                row = symbol_to_row.get(symbol)
                if row is None:
                    continue
                rows.append(row)
                returns: dict[str, float | None] = {}
                for label, start in periods.items():
                    values = valid_return(prices[[row], :], start, end)
                    returns[label] = round(float(values[0]), 6) if np.isfinite(values[0]) else None
                latest_mcap = mcaps[row, end] if end < mcaps.shape[1] else np.nan
                stocks.append(
                    {
                        "ticker": symbol,
                        "company": raw.companies[row],
                        "gicsSector": raw.sectors[row],
                        "gicsIndustry": raw.industries[row],
                        "stage": stage["key"],
                        "confidence": confidence,
                        "rationale": RATIONALES.get(symbol, stage["description"]),
                        "returns": returns,
                        "latestMcap": round(float(latest_mcap), 3) if np.isfinite(latest_mcap) else None,
                    }
                )
        stage_rows[stage["key"]] = rows

    modes: dict[str, Any] = {}
    for mode in ("Core", "Expanded"):
        stage_data: dict[str, Any] = {}
        for stage in STAGES:
            allowed = set(stage["core"] if mode == "Core" else stage["core"] + stage["adjacent"])
            members = [symbol_to_row[symbol] for symbol in allowed if symbol in symbol_to_row]
            series = chain_series(prices, mcaps, members, dates)
            performance: dict[str, Any] = {}
            for label, start in periods.items():
                member_returns = valid_return(prices[members, :], start, end)
                valid = member_returns[np.isfinite(member_returns)]
                basket_return = series_return(series, start, end)
                benchmark_return = benchmark_returns[label]
                performance[label] = {
                    "return": basket_return,
                    "relative": round(basket_return - benchmark_return, 6)
                    if basket_return is not None and benchmark_return is not None
                    else None,
                    "breadth": round(float(np.mean(valid > 0)), 6) if len(valid) else None,
                    "median": round(float(np.median(valid)), 6) if len(valid) else None,
                    "dispersion": round(float(np.std(valid)), 6) if len(valid) else None,
                    "members": int(len(valid)),
                }
            stage_data[stage["key"]] = {"series": series, "performance": performance, "members": len(members)}
        modes[mode] = stage_data

    stage_meta = [
        {key: stage[key] for key in ("key", "name", "short", "color", "description")}
        | {"coreCount": sum(1 for symbol in stage["core"] if symbol in symbol_to_row),
           "expandedCount": sum(1 for symbol in stage["core"] + stage["adjacent"] if symbol in symbol_to_row)}
        for stage in STAGES
    ]
    return {
        "meta": {
            "title": "S&P 500 AI 밸류체인 로테이션 모니터",
            "asOf": dates[-1].isoformat(),
            "startDate": dates[0].isoformat(),
            "endDate": dates[-1].isoformat(),
            "spxMembers": len(raw.tickers),
            "priceField": "병합된 Bloomberg 구성종목 Price",
            "source": raw.source,
        },
        "dates": [value.isoformat() for value in dates],
        "periodStarts": {key: dates[value].isoformat() for key, value in periods.items()},
        "benchmark": {"series": benchmark_series, "returns": benchmark_returns},
        "stages": stage_meta,
        "modes": modes,
        "stocks": stocks,
        "sources": SOURCES,
        "notes": [
            "각 바스켓의 집계가격은 Σ(Price×Shares)/ΣShares이며 배당은 제외한다. 현재 원자료의 Shares는 Market Cap/Price로 역산한다.",
            "비교지수는 현재 S&P 500 Raw 패널 전체 종목의 주식수 가중 집계가격이다.",
            "1개월·3개월·6개월은 달력상 같은 날짜 또는 그 이전의 최근 실제 거래일을 사용하며, 휴일·carry-forward 열은 제외한다.",
            "APH의 2026-09-02 2대1 주식배당 전후 가격 기준은 보고용 계산에서만 연속되도록 보정하며 Master 원본은 바꾸지 않는다.",
            "현재 구성종목을 과거로 소급하므로 생존편향이 있으며, 매매 가능한 백테스트가 아니라 로테이션 모니터링용이다.",
            "Alphabet은 발행사 이중가중을 피하기 위해 GOOGL만 포함하고 GOOG는 제외한다.",
            "Core는 직접 노출도가 높은 종목이며 Core+Adjacent는 의미 있는 2차 수혜주를 추가한다. 12개 분류는 분석 목적의 판단이며 지수사업자 공식 분류가 아니다.",
        ],
    }


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>S&P 500 AI 밸류체인 로테이션 모니터</title>
<style>
:root{--ink:#172033;--muted:#687386;--line:#dce2ea;--panel:#fff;--soft:#f5f7fa;--accent:#2563eb;--pos:#15803d;--neg:#dc2626}*{box-sizing:border-box}body{margin:0;background:#eef2f6;color:var(--ink);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}.page{max-width:1580px;margin:auto;padding:20px}.header{background:linear-gradient(125deg,#0b172d,#183b6b);color:#fff;border-radius:18px;padding:24px 28px;box-shadow:0 12px 30px #10284a24}.header h1{margin:0 0 5px;font-size:28px}.header p{margin:0;color:#d7e4f4}.controls,.tabs{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:14px 0}.controls label{font-size:12px;color:var(--muted);font-weight:700}.pill,button{border:1px solid var(--line);background:#fff;padding:7px 11px;border-radius:999px;cursor:pointer;color:var(--ink)}button.active{background:#172033;color:#fff;border-color:#172033}.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 4px 14px #1720330a}.grid{display:grid;grid-template-columns:1.08fr .92fr;gap:14px}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px}.kpi small{display:block;color:var(--muted)}.kpi strong{display:block;font-size:20px;margin-top:3px}.section{display:none}.section.active{display:block}h2{font-size:18px;margin:0 0 4px}h3{font-size:15px;margin:0 0 10px}.sub{color:var(--muted);font-size:12px;margin-bottom:12px}.barrow{display:grid;grid-template-columns:170px 1fr 70px 70px;align-items:center;gap:8px;margin:9px 0}.barwrap{height:22px;position:relative;background:linear-gradient(to right,transparent 49.85%,#172033 49.85%,#172033 50.15%,transparent 50.15%)}.bar{position:absolute;height:16px;top:3px;border-radius:3px;min-width:2px}.bar.pos{left:50%}.bar.neg{right:50%}.num{text-align:right;font-variant-numeric:tabular-nums}.posText{color:var(--pos)}.negText{color:var(--neg)}svg{width:100%;display:block}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px}.heatgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.tile{border-radius:9px;padding:10px;min-height:76px;border:1px solid #ffffff80}.tile b,.tile span{display:block}.tile span{font-size:12px;margin-top:4px}.stageTitle{grid-column:1/-1;font-weight:800;margin-top:8px;border-bottom:2px solid var(--line);padding-bottom:4px}.tablewrap{overflow:auto;max-height:650px}.datatable{width:100%;border-collapse:collapse;min-width:1050px}.datatable th{position:sticky;top:0;background:#eef2f6;text-align:left;border-bottom:1px solid var(--line);padding:8px}.datatable td{border-bottom:1px solid #edf0f4;padding:8px;vertical-align:top}.datatable .r{text-align:right;font-variant-numeric:tabular-nums}.source{padding:9px 0;border-bottom:1px solid var(--line)}.source a{font-weight:700;color:#1d4ed8;text-decoration:none}.method{background:#fff8e8;border:1px solid #f2d59b;border-radius:12px;padding:13px;margin-top:14px;font-size:12px}.tag{font-size:11px;border-radius:999px;background:#e9eef5;padding:3px 7px;white-space:nowrap}.tooltip{position:fixed;pointer-events:none;background:#101827;color:#fff;padding:8px 10px;border-radius:8px;font-size:12px;display:none;z-index:5;max-width:280px}@media(max-width:900px){.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.heatgrid{grid-template-columns:repeat(2,1fr)}.barrow{grid-template-columns:125px 1fr 60px 55px}.page{padding:10px}}
</style></head><body><div class="page">
<div class="header"><h1>S&P 500 AI 밸류체인 로테이션 모니터</h1><p id="subtitle"></p></div>
<div class="controls"><label>종목 범위</label><button data-mode="Core" class="active">핵심 종목</button><button data-mode="Expanded">핵심 + 인접 종목</button><label style="margin-left:10px">기간</label><span id="periods"></span></div>
<div class="tabs"><button data-tab="overview" class="active">로테이션 개요</button><button data-tab="timeline">상대성과 추이</button><button data-tab="heatmap">종목 히트맵</button><button data-tab="universe">분류 종목·근거</button></div>
<div id="kpis" class="kpis"></div>
<section id="overview" class="section active"><div class="grid"><div class="panel"><h2>AI 밸류체인 수익률 순위</h2><div class="sub">주식수 가중 집계가격 수익률. 오른쪽 숫자는 같은 방식의 S&P 500 대비 초과수익률.</div><div id="bars"></div></div><div class="panel"><h2>로테이션 맵</h2><div class="sub">x축은 3개월 초과수익률, y축은 선택 기간 초과수익률. 원 크기는 유효 종목 수.</div><svg id="scatter" viewBox="0 0 680 430"></svg></div></div></section>
<section id="timeline" class="section"><div class="panel"><h2>주식수 가중 S&P 500 집계가격 대비 상대성과</h2><div class="sub">선택 기간 시작점을 0%로 환산. 양수이면 해당 밸류체인이 주식수 가중 S&P 500 집계가격을 상회했다는 뜻이다.</div><div id="timelineLegend" class="legend"></div><svg id="lines" viewBox="0 0 1450 650"></svg></div></section>
<section id="heatmap" class="section"><div class="panel"><h2>구성종목 수익률 히트맵</h2><div class="sub">12개 밸류체인 안에서 선택 기간 수익률 순으로 정렬한다.</div><div id="heatgrid" class="heatgrid"></div></div></section>
<section id="universe" class="section"><div class="panel"><h2>분류 종목</h2><div class="sub">종목마다 하나의 주된 밸류체인만 부여해 중복 집계를 막았다.</div><div class="tablewrap"><table class="datatable"><thead><tr><th>밸류체인</th><th>티커</th><th>회사명</th><th>순수도</th><th>GICS 섹터</th><th>편입 근거</th><th class="r">1개월</th><th class="r">3개월</th><th class="r">6개월</th></tr></thead><tbody id="stockRows"></tbody></table></div></div><div class="panel" style="margin-top:14px"><h2>분류 참고자료</h2><div id="sources"></div></div></section>
<div id="method" class="method"></div></div><div id="tip" class="tooltip"></div>
<script>const DATA=__DATA__;
const S={mode:'Core',period:'1M',tab:'overview'};const stageBy=Object.fromEntries(DATA.stages.map(x=>[x.key,x]));
const periods=['1W','1M','3M','6M','YTD','Since 2025-07-01'];const periodLabel={'1W':'1주','1M':'1개월','3M':'3개월','6M':'6개월','YTD':'연초 이후','Since 2025-07-01':'2025년 7월 이후'};const modeLabel={Core:'핵심 종목',Expanded:'핵심 + 인접 종목'};const confidenceLabel={Core:'핵심',Adjacent:'인접'};const gicsLabel={'Information Technology':'정보기술','Communication Services':'커뮤니케이션 서비스','Consumer Discretionary':'경기소비재','Industrials':'산업재','Utilities':'유틸리티','Real Estate':'부동산','Financials':'금융','Consumer Staples':'필수소비재','Health Care':'헬스케어','Materials':'소재','Energy':'에너지'};const pct=x=>x==null?'—':`${x>=0?'+':''}${(x*100).toFixed(1)}%`;const cls=x=>x>=0?'posText':'negText';
document.getElementById('subtitle').textContent=`기준일 ${DATA.meta.asOf} · S&P 500 ${DATA.meta.spxMembers}개 증권 · Bloomberg 종목 가격 ${DATA.meta.startDate}~${DATA.meta.endDate} · 12개 밸류체인`;
document.getElementById('periods').innerHTML=periods.map(p=>`<button data-period="${p}" class="${p==='1M'?'active':''}">${periodLabel[p]}</button>`).join('');
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{S.mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>x.classList.toggle('active',x===b));render()});
document.querySelectorAll('[data-period]').forEach(b=>b.onclick=()=>{S.period=b.dataset.period;document.querySelectorAll('[data-period]').forEach(x=>x.classList.toggle('active',x===b));render()});
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{S.tab=b.dataset.tab;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.section').forEach(x=>x.classList.toggle('active',x.id===S.tab));render()});
function stageStats(){return DATA.stages.map(m=>({...m,...DATA.modes[S.mode][m.key].performance[S.period],series:DATA.modes[S.mode][m.key].series})).sort((a,b)=>(b.return??-99)-(a.return??-99))}
function renderKpis(stats){const top=stats[0],bot=stats.at(-1),bench=DATA.benchmark.returns[S.period];const broad=stats.reduce((a,x)=>a+(x.breadth??0),0)/stats.length;document.getElementById('kpis').innerHTML=`<div class="kpi"><small>${periodLabel[S.period]} 선도 밸류체인</small><strong>${top.short}</strong><span class="${cls(top.return)}">${pct(top.return)}</span></div><div class="kpi"><small>후행 밸류체인</small><strong>${bot.short}</strong><span class="${cls(bot.return)}">${pct(bot.return)}</span></div><div class="kpi"><small>주식수 가중 S&P 500</small><strong>${pct(bench)}</strong><span>${periodLabel[S.period]} 집계가격 수익률</span></div><div class="kpi"><small>평균 상승종목 비율</small><strong>${pct(broad)}</strong><span>${modeLabel[S.mode]} 기준</span></div>`}
function renderBars(stats){const max=Math.max(.01,...stats.flatMap(x=>[Math.abs(x.return||0),Math.abs(x.relative||0)]));document.getElementById('bars').innerHTML=stats.map(x=>{const w=Math.abs(x.return||0)/max*48;return `<div class="barrow"><div><b>${x.short}</b><br><span class="tag">${x.members}종목 · 상승비율 ${pct(x.breadth)}</span></div><div class="barwrap"><span class="bar ${x.return>=0?'pos':'neg'}" style="width:${w}%;background:${x.color}"></span></div><div class="num ${cls(x.return)}"><b>${pct(x.return)}</b></div><div class="num ${cls(x.relative)}">${pct(x.relative)}</div></div>`}).join('')}
function svgEl(n,a={}){const e=document.createElementNS('http://www.w3.org/2000/svg',n);Object.entries(a).forEach(([k,v])=>e.setAttribute(k,v));return e}function clear(e){while(e.firstChild)e.removeChild(e.firstChild)}
function renderScatter(stats){const svg=document.getElementById('scatter');clear(svg);const W=680,H=430,m={l:65,r:25,t:25,b:48};const pts=stats.map(x=>({x:DATA.modes[S.mode][x.key].performance['3M'].relative||0,y:x.relative||0,...x}));let lim=Math.max(.04,...pts.flatMap(p=>[Math.abs(p.x),Math.abs(p.y)]))*1.18;const sx=x=>m.l+(x+lim)/(2*lim)*(W-m.l-m.r),sy=y=>H-m.b-(y+lim)/(2*lim)*(H-m.t-m.b);[-lim,-lim/2,0,lim/2,lim].forEach(v=>{svg.append(svgEl('line',{x1:sx(v),x2:sx(v),y1:m.t,y2:H-m.b,stroke:v===0?'#111827':'#e5e7eb','stroke-width':v===0?1.8:1}));svg.append(svgEl('line',{x1:m.l,x2:W-m.r,y1:sy(v),y2:sy(v),stroke:v===0?'#111827':'#e5e7eb','stroke-width':v===0?1.8:1}))});pts.forEach(p=>{const c=svgEl('circle',{cx:sx(p.x),cy:sy(p.y),r:8+Math.sqrt(p.members)*2,fill:p.color,'fill-opacity':.78,stroke:'#fff','stroke-width':2});c.onmousemove=e=>tip(e,`<b>${p.name}</b><br>3개월 초과수익률 ${pct(p.x)}<br>${periodLabel[S.period]} 초과수익률 ${pct(p.y)}<br>유효 종목 ${p.members}개`);c.onmouseleave=hideTip;svg.append(c);const t=svgEl('text',{x:sx(p.x)+13,y:sy(p.y)-10,'font-size':12,fill:'#263247'});t.textContent=p.short;svg.append(t)});const xl=svgEl('text',{x:W/2,y:H-10,'text-anchor':'middle',fill:'#64748b'});xl.textContent='3개월 초과수익률';svg.append(xl);const yl=svgEl('text',{x:15,y:H/2,transform:`rotate(-90 15 ${H/2})`,'text-anchor':'middle',fill:'#64748b'});yl.textContent=`${periodLabel[S.period]} 초과수익률`;svg.append(yl)}
function selectedStart(){return DATA.periodStarts[S.period]}function sliceSeries(series){const start=selectedStart();return series.filter(x=>x[0]>=start)}
function renderLines(stats){const svg=document.getElementById('lines');clear(svg);const W=1450,H=650,m={l:70,r:30,t:25,b:50};const bench=Object.fromEntries(sliceSeries(DATA.benchmark.series).map(x=>x));const lines=stats.map(s=>{const vals=sliceSeries(s.series);const first=vals[0][1],b0=bench[vals[0][0]];return {...s,vals:vals.map(v=>[v[0],v[1]/first-bench[v[0]]/b0])}});let min=Math.min(0,...lines.flatMap(x=>x.vals.map(v=>v[1]))),max=Math.max(0,...lines.flatMap(x=>x.vals.map(v=>v[1])));const pad=Math.max(.01,(max-min)*.12);min-=pad;max+=pad;const n=Math.max(...lines.map(x=>x.vals.length));const sx=i=>m.l+i/Math.max(1,n-1)*(W-m.l-m.r),sy=y=>H-m.b-(y-min)/(max-min)*(H-m.t-m.b);for(let i=0;i<6;i++){const v=min+(max-min)*i/5;svg.append(svgEl('line',{x1:m.l,x2:W-m.r,y1:sy(v),y2:sy(v),stroke:Math.abs(v)<(max-min)/12?'#111827':'#e5e7eb','stroke-width':Math.abs(v)<(max-min)/12?1.7:1}));const t=svgEl('text',{x:m.l-8,y:sy(v)+4,'text-anchor':'end',fill:'#64748b'});t.textContent=pct(v);svg.append(t)}lines.forEach(l=>{let d='';l.vals.forEach((v,i)=>d+=`${i?'L':'M'}${sx(i)},${sy(v[1])}`);const p=svgEl('path',{d,fill:'none',stroke:l.color,'stroke-width':2.5});p.onmousemove=e=>tip(e,`<b>${l.name}</b><br>최근 초과수익률 ${pct(l.vals.at(-1)[1])}`);p.onmouseleave=hideTip;svg.append(p)});document.getElementById('timelineLegend').innerHTML=lines.map(l=>`<span><i class="dot" style="background:${l.color}"></i>${l.short} ${pct(l.vals.at(-1)[1])}</span>`).join('')}
function color(v){if(v==null)return '#eef2f6';const a=Math.min(1,Math.abs(v)/.25);return v>=0?`rgba(22,163,74,${.12+.72*a})`:`rgba(220,38,38,${.12+.72*a})`}function renderHeat(){const allowed=S.mode==='Core'?['Core']:['Core','Adjacent'];const stocks=DATA.stocks.filter(x=>allowed.includes(x.confidence));let out='';DATA.stages.forEach(st=>{out+=`<div class="stageTitle" style="border-color:${st.color}">${st.name}</div>`;stocks.filter(x=>x.stage===st.key).sort((a,b)=>(b.returns[S.period]??-99)-(a.returns[S.period]??-99)).forEach(x=>out+=`<div class="tile" style="background:${color(x.returns[S.period])}" title="${x.rationale.replaceAll('"','&quot;')}"><b>${x.ticker} · ${pct(x.returns[S.period])}</b><span>${x.company}</span><span>${confidenceLabel[x.confidence]}</span></div>`) });document.getElementById('heatgrid').innerHTML=out}
function renderUniverse(){const order=Object.fromEntries(DATA.stages.map((x,i)=>[x.key,i]));document.getElementById('stockRows').innerHTML=[...DATA.stocks].sort((a,b)=>order[a.stage]-order[b.stage]||a.confidence.localeCompare(b.confidence)||a.ticker.localeCompare(b.ticker)).map(x=>`<tr><td>${stageBy[x.stage].short}</td><td><b>${x.ticker}</b></td><td>${x.company}</td><td><span class="tag">${confidenceLabel[x.confidence]}</span></td><td>${gicsLabel[x.gicsSector]||x.gicsSector}</td><td>${x.rationale}</td><td class="r ${cls(x.returns['1M'])}">${pct(x.returns['1M'])}</td><td class="r ${cls(x.returns['3M'])}">${pct(x.returns['3M'])}</td><td class="r ${cls(x.returns['6M'])}">${pct(x.returns['6M'])}</td></tr>`).join('');document.getElementById('sources').innerHTML=DATA.sources.map(x=>`<div class="source"><a href="${x[1]}" target="_blank" rel="noopener">${x[0]}</a><br><span class="sub">${x[2]}</span></div>`).join('')}
function tip(e,s){const t=document.getElementById('tip');t.innerHTML=s;t.style.display='block';t.style.left=Math.min(innerWidth-300,e.clientX+15)+'px';t.style.top=Math.min(innerHeight-100,e.clientY+15)+'px'}function hideTip(){document.getElementById('tip').style.display='none'}
function render(){const stats=stageStats();renderKpis(stats);if(S.tab==='overview'){renderBars(stats);renderScatter(stats)}if(S.tab==='timeline')renderLines(stats);if(S.tab==='heatmap')renderHeat();if(S.tab==='universe')renderUniverse()}
document.getElementById('method').innerHTML='<b>방법론과 한계</b><br>'+DATA.notes.join(' ');renderUniverse();render();</script></body></html>'''


def build(output_path: Path | None, sources: list[Path] | None = None) -> dict[str, Any]:
    raw = load_spx(sources)
    data = build_data(raw)
    if output_path is None:
        tag = data["meta"]["asOf"].replace("-", "")
        output_path = THEME_DIR / "output" / tag / "AI" / "SP500_AI_Value_Chain_Rotation.html"
    else:
        output_path = output_path.resolve()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    output = HTML_TEMPLATE.replace("__DATA__", payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(f"output={output_path}")
    print(f"as_of={data['meta']['asOf']} stocks={len(data['stocks'])} stages={len(data['stages'])}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional HTML path. Default: Theme/output/<data YYYYMMDD>/AI/.",
    )
    parser.add_argument("sources", nargs="*", type=Path)
    args = parser.parse_args()
    build(args.output, sources=args.sources or None)


if __name__ == "__main__":
    main()
