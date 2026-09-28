# Top10 / Down10 최신 자동 업데이트 — 전체 코드

이 문서는 특정 날짜와 특정 Raw 파일명에 의존하지 않는 운영 코드를 한 파일에 모은 것이다. 새 BQuant 파일을 `Rawfile/Daily_Input`에 넣고 `Rawfile/update_all.ps1`을 실행하면 단일 Master가 갱신되고, 지수별 최신 유효 거래일과 최근 10거래일 구간을 자동으로 다시 선택한다.

## 핵심 동작

- 입력: `Rawfile/BQuant_Master.xlsx`
- 종료일: 구성종목 10% 초과의 가격이 실제로 움직인 마지막 행
- 시작일: 종료일까지 최근 11개 유효 종가 중 첫 번째 값
- 수익률: 10개 거래구간의 현지통화 단순 가격수익률, 배당 제외
- 최신 포인터: `Market_10D_Rankings_latest.json`, `output/latest_outputs.json`
- 산출물 파일명: 데이터 기준일을 `YYYYMMDD`로 자동 부여

## 실행

```powershell
.\run_top10_update.ps1
```

특정 통합 Master를 직접 사용할 때만 경로를 넘긴다.

```powershell
.\run_top10_update.ps1 'C:\data\Bquant_new_snapshot.xlsb'
```

## 포함 파일

- `compute_10d_rankings.py`: 단일 Master를 읽고 최신 유효 거래일 기준 Top/Down 10 계산
- `build_market_10d_outputs.py`: 동적 기준일로 차트·Excel·enriched JSON 생성
- `build_market_10d_report.js`: latest JSON을 읽고 동적 파일명으로 Word 보고서 생성
- `validate_market_10d_workbook.py`: latest_outputs.json이 가리키는 Excel 검증
- `render_market_10d_report.py`: latest_outputs.json이 가리키는 PDF 렌더링
- `run_top10_update.ps1`: 계산부터 검증까지 한 번에 실행

---

## compute_10d_rankings.py

단일 Master를 읽고 최신 유효 거래일 기준 Top/Down 10 계산.

````python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
BQL_DIR = HERE.parents[1]
RAWFILE_DIR = BQL_DIR / "Rawfile"
MASTER_PATH = RAWFILE_DIR / "BQuant_Master.xlsx"
DEFAULT_OUT = HERE / "Market_10D_Rankings_latest.json"
TARGETS = ("SPX", "SHSZ300", "SXXP")

sys.path.insert(0, str(BQL_DIR / "유로존_dashboard"))
import build_market_rotation_dashboard as raw_builder  # noqa: E402


def automatic_sources() -> list[Path]:
    """All production dashboards use one consolidated workbook."""
    if not MASTER_PATH.exists():
        raise FileNotFoundError(
            f"Master workbook not found: {MASTER_PATH}. "
            "Put the daily BQuant file in Rawfile/Daily_Input and run Rawfile/update_all.ps1."
        )
    return [MASTER_PATH]


def load_targets(sources: list[Path]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for source in sources:
        for raw in raw_builder.iter_raw_indices(source):
            if raw.code not in TARGETS:
                continue
            merged[raw.code] = (
                raw
                if raw.code not in merged
                else raw_builder.merge_raw_indices(merged[raw.code], raw)
            )
    missing = sorted(set(TARGETS) - set(merged))
    if missing:
        raise KeyError(f"Missing target indices: {missing}")
    return merged


def trading_sessions(prices: np.ndarray) -> list[int]:
    """Return actual sessions: >10% of valid constituents changed from prior row."""
    sessions: list[int] = []
    for j in range(1, prices.shape[1]):
        ok = np.isfinite(prices[:, j]) & np.isfinite(prices[:, j - 1]) & (prices[:, j - 1] != 0)
        if not ok.any():
            continue
        changed = ~np.isclose(prices[ok, j], prices[ok, j - 1], rtol=1e-7, atol=1e-9)
        if float(changed.mean()) > 0.10:
            sessions.append(j)
    return sessions


def record(raw, i: int, start: int, end: int, total_mcap: float) -> dict:
    start_price = float(raw.metrics["price"][i, start])
    end_price = float(raw.metrics["price"][i, end])
    mcap = float(raw.metrics["mcap"][i, end])
    return {
        "Ticker": raw.tickers[i],
        "Security_Name": raw.companies[i],
        "GICS_Sector": raw.sectors[i],
        "GICS_Industry_Group": raw.industries[i],
        "Price": end_price,
        "Index_Weight": mcap / total_mcap if np.isfinite(mcap) and total_mcap > 0 else None,
        "Price_start": start_price,
        "Return_10D": end_price / start_price - 1,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate current Top/Down 10 from the latest 11 valid price sessions."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        help="Optional BQuant workbooks. Omit to use Incremental baseline + archive automatically.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sources = [path.resolve() for path in args.sources] if args.sources else automatic_sources()
    raws = load_targets(sources)
    result: dict[str, dict] = {}
    for code in TARGETS:
        raw = raws[code]
        prices = raw.metrics["price"]
        sessions = trading_sessions(prices)
        if len(sessions) < 11:
            raise ValueError(f"{raw.code}: fewer than 11 valid trading sessions")
        end, start = sessions[-1], sessions[-11]
        ok = np.isfinite(prices[:, start]) & np.isfinite(prices[:, end]) & (prices[:, start] > 0)
        mcap = raw.metrics["mcap"][:, end]
        total_mcap = float(np.sum(mcap[np.isfinite(mcap) & (mcap > 0)]))
        rows = [record(raw, i, start, end, total_mcap) for i in np.flatnonzero(ok)]
        rows.sort(key=lambda item: item["Return_10D"], reverse=True)
        result[raw.code] = {
            "start": raw.dates[start].isoformat(),
            "latest": raw.dates[end].isoformat(),
            "constituents": len(rows),
            "top": rows[:10],
            "bottom": list(reversed(rows[-10:])),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.write_text(payload, encoding="utf-8")
    as_of = max(block["latest"] for block in result.values())
    dated_copy = args.output.with_name(f"Market_10D_Rankings_{as_of.replace('-', '')}.json")
    if dated_copy != args.output:
        dated_copy.write_text(payload, encoding="utf-8")
    print(f"OUTPUT={args.output}")
    print(f"AS_OF={as_of}")
    print("SOURCES=" + ";".join(str(path) for path in sources))
    for code in TARGETS:
        block = result[code]
        print(f"{code}: {block['start']} -> {block['latest']} ({block['constituents']} stocks)")


if __name__ == "__main__":
    main()
````

## build_market_10d_outputs.py

동적 기준일로 차트·Excel·enriched JSON 생성.

````python
import argparse
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xlsxwriter


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "Market_10D_Rankings_latest.json"
OUT_DIR = HERE / "output"
XLSX_PATH = OUT_DIR / "SPX_CSI300_STOXX600_10D_Top10_Down10_latest.xlsx"
ENRICHED_PATH = OUT_DIR / "Market_10D_Enriched_latest.json"
CHART_DIR = OUT_DIR / "charts"

HISTORICAL_REASON_WINDOWS = {
    "SPX": ("2026-08-17", "2026-08-31"),
    "SHSZ300": ("2026-08-18", "2026-09-01"),
    "SXXP": ("2026-08-18", "2026-09-01"),
}


SOURCES = {
    "S1": ("Merck·Moderna INTerpath-001 Phase 3 발표", "https://www.merck.com/media/news/"),
    "S2": ("Salesforce FY27 Q2 실적 발표", "https://www.salesforce.com/news/press-releases/2026/08/26/fy27-q2-earnings/"),
    "S3": ("Veeva FY27 Q2 8-K", "https://www.sec.gov/Archives/edgar/data/1393052/000139305226000032/veev-20260826.htm"),
    "S4": ("Estée Lauder FY2026 실적", "https://www.sec.gov/Archives/edgar/data/1001250/000100125026000038/elq4fy2026exhibit991.htm"),
    "S5": ("California utility stocks and SB 492", "https://www.spglobal.com/market-intelligence/en/news-insights/articles/2026/8/california-utility-stocks-slide-on-wildfire-legislation-105564049"),
    "S6": ("AI hardware rotation on Aug. 18", "https://247wallst.com/investing/2026/08/18/coherent-teradyne-and-ciena-are-the-sp-500s-3-biggest-decliners-on-tuesday/"),
    "S7": ("Mango TV AI-produced drama catalyst", "https://www.itiger.com/news/1177669587"),
    "S8": ("World Gold Council China gold update", "https://www.gold.org/goldhub/gold-focus/2026/08/china-gold-market-update-strong-official-sector-buying-july"),
    "S9": ("Shandong Gold H1 profitability", "https://ca.investing.com/news/stock-market-news/why-is-shandong-gold-mining-stock-surging-today-93CH-4822472"),
    "S10": ("Envicool business and H1 context", "https://hk.marketscreener.com/news/shenzhen-envicool-technology-co-ltd-reports-earnings-results-for-the-half-year-ended-june-30-202-ce7858dbdc8eff2d"),
    "S11": ("A-share semiconductor and optical-tech pullback", "https://www.yicai.com/news/103331444.html"),
    "S12": ("Citi positive catalyst watch on BMW", "https://de.investing.com/news/stock-market-news/citi-setzt-bmw-und-forvia-auf-positive-catalyst-watch-3641488"),
    "S13": ("Deutsche Börse August 2026 trading volume", "https://www.cashmarket.deutsche-boerse.com/cash-de/Informieren/veroeffentlichungen/pressemitteilungen/Deutsche-B-rse-Umsatzstatistik-f-r-August-2026-5537184"),
    "S14": ("DAX selling: Siemens Energy and Rheinmetall", "https://eurotelegraph.eu/markets/european-shares/2026/08/31/dax-leads-euro-stoxx-slide-as-siemens-energy-rheinmetall-drop"),
    "S15": ("Hochschild Mining 2026 interim results", "https://www.hochschildmining.com/investors/results-reports-presentations"),
    "S16": ("FLSmidth H1 2026 interim report", "https://fls.com/en/announcements/2026/flsmidth-h1-2026-interim-financial-report-continued-strong-order-growth-and-higher-revenue-conversion-support-full-year-guidance-adjustment"),
    "S17": ("SalMar Q2 2026 reports and announcements", "https://www.salmar.no/en/investor/reports-presentations/"),
    "S18": ("Dino Polska H1 2026 financial reports", "https://grupadino.pl/en/financial-reports/"),
    "S19": ("Swissquote H1 2026 financial report", "https://www.swissquote.com/en/group/investor-relations/financial-reports"),
    "S20": ("Novonesis H1 2026 results", "https://www.novonesis.com/es/news/h1-2026-novonesis-delivered-strong-8-organic-sales-growth-and-increases-full-year-outlook"),
    "S21": ("Drax H1 2026 results", "https://www.drax.com/financial-news/half-year-results-for-the-six-months-ended-30-june-2026/"),
    "S22": ("Sartorius Stedim Biotech H1 2026 results", "https://www.sartorius.com/en/company/newsroom/corporate-news/2026-half-year-results-sartorius-stedim-biotech-1845882"),
    "S23": ("European defence shares sell-off, 31 Aug 2026", "https://www.finanzen.net/amp/aktien/sektorschwaeche-ausverkauf-bei-deutschen-ruestungsaktien-warum-rheinmetall-renk-hensoldt-tkms-nachgeben-00-15910423"),
    "S24": ("AI hardware valuation and positioning reset", "https://www.morningstar.com.au/stocks/why-great-earnings-havent-been-good-enough-ai-hardware-stocks"),
    "S25": ("SES H1 2026 results and outlook", "https://www.ses.com/news/press-release/ses-reports-h1-2026-results-reiterates-fullyear-outlook"),
    "S26": ("ROCKWOOL H1 2026 results", "https://www.rockwool.com/group/about-us/news/2026/rockwool-releases-h1-2026-results/"),
    "S27": ("K+S H1 2026 financial publications", "https://www.kpluss.com/de-de/investor-relations/publikationen/finanzpublikationen/"),
    "S28": ("Pan African Resources FY2026 operational update", "https://www.panafricanresources.com/wp-content/uploads/2026/06/SENS_PAN_Operational-update-ahead-of-the-year-ending-30-June-2026_20260601.pdf"),
    "S29": ("Comet H1 2026 results", "https://comet.tech/en/events/2026/half-year-results-presentation"),
}


REASONS = {
    # United States — winners
    "MRNA UW Equity": ("FACT", "Merck와 공동 개발한 개인맞춤형 암 백신 intismeran autogene의 3상에서 재발 없는 생존과 원격전이 없는 생존 목표를 충족했다. 임상 성공으로 파이프라인 가치가 재평가됐다.", "바이오 임상 이벤트", "S1"),
    "CRM UN Equity": ("FACT", "FY27 2분기 실적 발표에서 기록적 분기 성과와 상향된 전망을 제시했다. AI 에이전트 매출화가 단순 기대가 아니라 소프트웨어 매출과 마진으로 연결될 수 있다는 신뢰가 회복됐다.", "AI 소프트웨어 실적화", "S2"),
    "NOW UN Equity": ("INFERENCE", "기간 중 뚜렷한 단일 공시보다 Salesforce 호실적 이후 엔터프라이즈 소프트웨어 전반으로 매수세가 확산된 영향이 컸다. AI 지출의 수혜가 하드웨어에서 애플리케이션으로 이동한 흐름이다.", "AI 소프트웨어 로테이션", "S2"),
    "COIN UW Equity": ("INFERENCE", "가상자산 가격과 거래활동에 대한 고베타 노출이 반영된 움직임으로 판단한다. 기간 중 확인된 단일 기업 이벤트보다 암호자산 위험선호와 금융 플랫폼 베타가 주된 설명이다.", "크립토 베타", ""),
    "EL UN Equity": ("FACT", "FY2026 4분기 매출이 6%, 연간 매출이 5% 증가했고 모든 지역에서 성장했다. FY2027 유기적 매출 전망을 유지하면서 조정 영업마진 전망을 높여 턴어라운드 신뢰가 강화됐다.", "소비재 턴어라운드", "S4"),
    "VEEV UN Equity": ("FACT", "8월 26일 FY27 2분기 실적을 발표했다. 생명과학 클라우드 수요와 실적 가시성이 확인되며 헬스케어 소프트웨어의 방어적 성장 프리미엄이 확대됐다.", "헬스케어 소프트웨어", "S3"),
    "TYL UN Equity": ("INFERENCE", "회사 고유의 신규 대형 촉매보다 정부·공공부문 소프트웨어의 반복매출 특성과 소프트웨어 업종 리레이팅이 결합됐다.", "방어적 소프트웨어", "S2"),
    "ADBE UW Equity": ("INFERENCE", "AI가 기존 소프트웨어의 가격·사용량을 훼손한다는 우려에서, 생성형 AI가 제품 사용과 과금에 기여할 수 있다는 쪽으로 기대가 이동했다. 동기간 소프트웨어 팩터 강세의 일부다.", "생성형 AI 애플리케이션", "S2"),
    "CTSH UW Equity": ("INFERENCE", "소프트웨어·IT서비스 로테이션과 비용 효율화 기대가 반영됐다. 확인된 단일 이벤트보다 저평가 IT서비스로의 확산 성격이 강하다.", "IT서비스 리레이팅", "S2"),
    "MOS UN Equity": ("INFERENCE", "비료 가격과 농업 투입재 업황에 대한 기대가 소재주 매수로 연결됐다. 최근 실적의 이익 방어력은 긍정적이지만 판매량과 원가 변동성이 남아 있어 순수 실적 촉매로 단정하기 어렵다.", "비료·원자재", ""),
    # United States — losers
    "EIX UN Equity": ("FACT", "캘리포니아 SB 492가 유틸리티가 기대했던 포괄적 산불 배상책임 완화를 담지 못했다. 산불 관련 꼬리위험과 자본비용 부담이 다시 가격에 반영됐다.", "산불 배상책임", "S5"),
    "PCG UN Equity": ("FACT", "SB 492가 포괄적 산불 책임개혁에 미달했고, 신용등급 정상화 경로가 지연될 수 있다는 우려가 제기됐다. 규제 리스크가 실적보다 주가를 압도했다.", "산불 배상책임", "S5"),
    "TER UW Equity": ("FACT", "8월 18일 AI 인프라 종목에서 차익실현이 집중됐고 장기금리 상승이 고밸류 하드웨어의 할인율 부담을 키웠다. 실적 붕괴보다 포지셔닝과 멀티플 조정 성격이 강했다.", "AI 하드웨어 디레이팅", "S6"),
    "COHR UN Equity": ("FACT", "광통신·AI 인프라 주가가 큰 폭으로 선행 상승한 뒤 8월 18일 로테이션 매물이 집중됐다. 동종 AI 하드웨어와 함께 하락해 개별 수요 둔화보다 기대치 조정으로 보는 편이 타당하다.", "광통신 차익실현", "S6"),
    "FIX UN Equity": ("INFERENCE", "데이터센터 건설과 기계설비 수혜로 높은 기대가 반영된 종목군에서 차익실현이 발생했다. 장기금리 상승과 AI CAPEX 지속성 논쟁이 멀티플을 압박했다.", "데이터센터 건설 디레이팅", "S6"),
    "JBL UN Equity": ("INFERENCE", "전자제품 생산·서버 공급망의 AI 하드웨어 노출이 오히려 단기 약점으로 작용했다. 기간 중 하드웨어·반도체에서 소프트웨어로 자금이 이동한 영향이다.", "AI 서버 공급망 차익실현", "S6"),
    "STX UW Equity": ("INFERENCE", "AI 스토리지 수요 기대를 선반영한 뒤 하드웨어 전반의 고밸류 조정에 동참했다. 수요 훼손이 확인됐다기보다 고모멘텀 포지션 축소의 성격이 강하다.", "AI 스토리지 디레이팅", "S6"),
    "GEV UN Equity": ("INFERENCE", "전력망·가스터빈·데이터센터 전력 수요의 구조적 논리는 유지됐지만, 대규모 수주 기대를 가격에 상당 부분 반영한 뒤 장기금리 상승과 AI 인프라 차익실현의 영향을 받았다.", "전력 인프라 기대치 조정", "S6"),
    "GNRC UN Equity": ("INFERENCE", "백업전력과 분산전원 기대가 선반영된 종목에서 AI 전력 인프라 포지션 축소가 나타났다. 개별 실적 충격보다 관련 바스켓 매도의 영향이 컸다.", "백업전력 차익실현", "S6"),
    "FLEX UW Equity": ("INFERENCE", "데이터센터·전자 제조서비스 노출로 AI 공급망 바스켓에 포함됐으나, 하드웨어에서 소프트웨어로의 단기 로테이션이 역풍이 됐다.", "AI 제조공급망 차익실현", "S6"),

    # China — winners
    "300413 CH Equity": ("FACT", "Mango TV의 AI 제작 드라마가 8월 31일 공개되며 AIGC가 실제 미디어 콘텐츠로 상용화된다는 기대가 부각됐다. 주가는 일일 상한가를 기록하며 10일 수익률 1위를 차지했다.", "AI 콘텐츠 애플리케이션", "S7"),
    "600547 CH Equity": ("FACT", "상반기 수익성 개선이 확인된 데다 중국 금 ETF 유입과 인민은행의 21개월 연속 금 매입이 금광주 프리미엄을 지지했다.", "금·실적 개선", "S8,S9"),
    "601319 CH Equity": ("INFERENCE", "보험의 자산운용 레버리지와 고배당·저평가 금융주 선호가 결합된 움직임이다. 기간 중 확인된 단일 기업 촉매보다 가치·배당 팩터 성격이 강하다.", "보험·고배당 가치", ""),
    "002837 CH Equity": ("FACT", "데이터센터용 정밀 온도제어·냉각 솔루션 업체라는 사업구조가 AI 서버 열관리 수요와 직접 연결된다. 상반기 실적 발표 구간에서 AI 냉각의 실적화 기대가 강화됐다.", "데이터센터 냉각", "S10"),
    "002493 CH Equity": ("INFERENCE", "정유·석유화학 가격과 원가 스프레드 개선 기대가 소재주 로테이션을 만들었다. 단일 기업 뉴스보다는 유가·화학 업황 베타로 해석한다.", "석유화학 업황", ""),
    "600039 CH Equity": ("INFERENCE", "도로·교량 건설 노출을 통해 경기부양과 인프라 집행 기대를 반영했다. 정책 기대는 주가의 하방을 지지하지만 신규수주와 현금회수 확인이 필요하다.", "중국 인프라 정책", ""),
    "300122 CH Equity": ("INFERENCE", "백신·바이오의 낮아진 기대와 헬스케어 반등이 결합됐다. 기간 중 확인된 단일 임상 이벤트보다 낙폭과대 업종 회복 성격이 강하다.", "헬스케어 낙폭과대", ""),
    "601998 CH Equity": ("INFERENCE", "고배당 은행과 정책금융 기대가 반영됐다. 대출 성장의 강한 가속이 확인됐다기보다 낮은 밸류에이션과 배당 안정성에 대한 선호다.", "은행·고배당 가치", ""),
    "300760 CH Equity": ("INFERENCE", "의료기기의 질적 성장과 해외 매출 방어력에 대한 선호가 헬스케어 회복과 맞물렸다. 개별 단기 뉴스보다 이익 방어력 재평가다.", "의료기기 질적 성장", ""),
    "601058 CH Equity": ("INFERENCE", "타이어 수출과 원가 경쟁력에 대한 기대가 자동차 부품주 내 차별화를 만들었다. 확인된 단일 이벤트보다 수출 제조업 알파의 성격이 강하다.", "타이어 수출", ""),
    # China — losers
    "300274 CH Equity": ("INFERENCE", "태양광 인버터·에너지저장장치의 고성장 기대가 선반영된 뒤 신재생 장비 전반에서 포지션 축소가 나타났다. 정책 수혜와 단기 주가 방향이 다를 수 있음을 보여준다.", "신재생 장비 디레이팅", "S11"),
    "002028 CH Equity": ("INFERENCE", "전력기기 고성장과 전력망 CAPEX 기대를 반영한 고밸류 종목에서 차익실현이 집중됐다. 수주 붕괴보다 혼잡도 완화 성격으로 본다.", "전력기기 차익실현", "S11"),
    "002353 CH Equity": ("INFERENCE", "유전서비스 업종 내 고변동성 포지션이 축소됐다. 유가 방향만으로 설명되지 않아 기업별 주문·마진 확인 전까지 원인을 단정하기 어렵다.", "에너지 서비스 디레이팅", ""),
    "002202 CH Equity": ("INFERENCE", "풍력장비의 가격경쟁과 수익성 우려가 신재생 장비 매도와 겹쳤다. 설치량 증가와 제조사 마진은 별개라는 점이 반영됐다.", "풍력장비 마진 우려", "S11"),
    "688082 CH Equity": ("INFERENCE", "반도체 장비의 실적이 기대에 부합하는 정도로는 높은 밸류에이션을 지지하기 어려워지며 매물이 출회됐다. 8월 24일 A주 반도체에서 집중 매도가 확인됐다.", "반도체 장비 조정", "S11"),
    "688472 CH Equity": ("INFERENCE", "태양광 제조 공급과잉·가격 경쟁 우려가 지속되며 신재생 장비 조정에 동참했다. 원자료의 GICS 분류는 반도체지만 경제적 노출은 태양광 모듈이다.", "태양광 공급과잉", "S11"),
    "000657 CH Equity": ("INFERENCE", "희소금속 가격과 정책 테마를 선반영한 뒤 차익실현이 발생했다. 구조적 국산화 논리보다 단기 모멘텀 축소가 주가를 지배했다.", "희소금속 차익실현", ""),
    "600584 CH Equity": ("INFERENCE", "후공정·패키징까지 반도체 업종 전반의 밸류에이션 재평가가 확산됐다. 개별 주문 훼손보다 A주 기술주 바스켓 매도 성격이다.", "반도체 패키징 조정", "S11"),
    "002371 CH Equity": ("INFERENCE", "국산 반도체 장비 대표주로서 높은 기대와 혼잡도가 역풍이 됐다. 업종 실적의 '기대 부합'만으로는 멀티플 유지가 어려웠다.", "반도체 장비 혼잡도", "S11"),
    "688072 CH Equity": ("INFERENCE", "증착 장비 국산화의 장기 논리는 남아 있지만 8월 기술주 2차 조정에서 고베타 장비주로 매도됐다.", "반도체 장비 조정", "S11"),

    # STOXX Europe 600 — winners
    "HOC LN Equity": ("FACT", "8월 26일 상반기 매출이 62%, 조정 EBITDA가 119% 증가했고 순부채에서 순현금으로 전환했다. 금 가격 강세에 실적 레버리지가 확인되며 금광주 프리미엄이 확대됐다.", "금광 실적 레버리지", "S15"),
    "FLS DC Equity": ("FACT", "8월 19일 발표한 2분기 유기적 매출은 16%, 수주는 13% 증가했고 조정 EBITA 마진은 17.3%로 상승했다. 연간 매출성장과 마진 가이던스 하단도 높였다.", "광산장비 실적·가이던스", "S16"),
    "PAF LN Equity": ("INFERENCE", "기간 중 확인된 핵심 신규 공시보다 금 가격과 귀금속 주식 베타가 주된 설명이다. 다만 FY2026 생산량이 약 40% 늘어난 사상 최고 수준이라는 운영 기반이 상승 탄력을 키웠다.", "금 가격·생산량", "S28"),
    "SDF GY Equity": ("INFERENCE", "8월 12일 연간 전망 상향 이후 비료·칼륨 가격과 낮아진 기대의 정상화가 이어졌다. 분석기간 안의 신규 이벤트보다는 실적 발표의 후행 반영 성격이 강하다.", "비료 가격·전망 상향", "S27"),
    "SALM NO Equity": ("FACT", "8월 25일 2분기 보고서에서 노르웨이 양식 부문의 강한 생물학적 성과를 제시했고 자사주 매입도 시작했다. 생산 정상화와 주주환원이 동시에 반영됐다.", "연어 생산 정상화·자사주", "S17"),
    "DNP PW Equity": ("FACT", "8월 20일 상반기 실적을 발표했다. 매장 확장과 방어적 식품소매 성장의 가시성이 경기민감주 변동성이 큰 구간에서 재평가됐다.", "식품소매 성장·방어력", "S18"),
    "SQN SE Equity": ("INFERENCE", "8월 13일 상반기 고객자산이 사상 최고 CHF 96.3bn, 신규자금이 CHF 5.1bn으로 확인된 뒤 고객 성장 프리미엄이 이어졌다. 다만 기간 시작 전 발표여서 후행 반영으로 분류했다.", "온라인 브로커 고객성장", "S19"),
    "NSISB DC Equity": ("FACT", "8월 19일 상반기 유기적 매출이 8% 증가했고 연간 성장 전망을 7~8%로 상향했다. EUR 1bn 자사주 매입도 발표해 실적과 자본환원이 함께 작용했다.", "바이오솔루션 전망 상향", "S20"),
    "DRX LN Equity": ("INFERENCE", "영국 전력안보와 유연성 자산의 희소성, 향후 데이터센터용 계통접속 옵션이 부각됐다. 10일 창 안의 단일 신규 공시보다 전력가격·정책 베타의 영향이 크다.", "전력안보·데이터센터 옵션", "S21"),
    "DIM FP Equity": ("INFERENCE", "7월 상반기 실적에서 반복소모품이 견조하고 장비가 소폭 성장으로 복귀한 점이 확인된 뒤 바이오프로세싱 회복 기대가 이어졌다. 기간 내 신규 대형 촉매는 확인되지 않았다.", "바이오프로세싱 회복", "S22"),
    # STOXX Europe 600 — losers
    "LDO IM Equity": ("INFERENCE", "Leonardo를 포함한 유럽 방산주가 동반 하락했다. 수주 논리의 붕괴보다 높은 기대와 정부 재정조달 우려 속에서 방산 바스켓의 혼잡도가 풀린 움직임으로 판단한다.", "유럽 방산 디레이팅", "S23"),
    "BESI NA Equity": ("INFERENCE", "첨단패키징과 AI 반도체 장비의 장기 수요는 유지됐지만, 높은 밸류에이션의 AI 하드웨어에서 차익실현이 이어졌다. 실적 훼손이 확인된 하락으로 보기는 어렵다.", "AI 반도체 장비 차익실현", "S24"),
    "HAG GY Equity": ("INFERENCE", "Rheinmetall·Saab·Leonardo와 함께 하락해 기업별 뉴스보다 방산 팩터 매도의 성격이 강했다. 주문잔고가 실제 매출·마진으로 전환되는 속도에 대한 요구가 높아졌다.", "유럽 방산 디레이팅", "S23"),
    "SAABB SS Equity": ("INFERENCE", "8월 21일 유럽 방산주 동반 약세가 확인됐고 이후 매도가 이어졌다. 재무가이던스 변화보다 높은 멀티플과 포지션 축소가 단기 주가를 지배했다.", "유럽 방산 디레이팅", "S23"),
    "COTN SE Equity": ("INFERENCE", "H1 실적은 양호했지만 반도체·AI 장비의 높아진 기대를 추가로 넘어설 촉매가 부족했다. 좋은 실적에도 밸류에이션이 압축되는 전형적인 혼잡도 완화로 해석한다.", "반도체 장비 멀티플 압축", "S29,S24"),
    "RHM GY Equity": ("INFERENCE", "8월 31일 독일 방산주 매도에서 Rheinmetall과 Hensoldt가 함께 하락했다. 약 EUR 80.5bn 주문잔고에도 주가가 내린 점은 수요 붕괴보다 기대치와 밸류에이션 조정에 가깝다.", "유럽 방산 디레이팅", "S23"),
    "QQ/ LN Equity": ("INFERENCE", "QinetiQ도 유럽 방산 바스켓 매도에 동참했다. 기간 중 확인된 독립적 대형 악재보다 정부 예산의 집행 속도와 고평가 우려가 공통 요인이다.", "유럽 방산 디레이팅", "S23"),
    "SESG FP Equity": ("INFERENCE", "H1 실적과 연간 전망 유지에도 위성사업 통합과 2026년 컨센서스 달성 난이도에 대한 우려가 남았다. 실적 발표 후 지속된 디레이팅의 성격이 강하다.", "위성사업 통합·컨센서스 우려", "S25"),
    "HO FP Equity": ("INFERENCE", "Thales 역시 유럽 방산주 동반 약세에 포함됐다. 높은 주문잔고보다 단기 매출 전환과 수익성 증명이 중요해지는 국면으로, 개별 수주 취소로 단정할 근거는 없다.", "유럽 방산 디레이팅", "S23"),
    "ROCKB DC Equity": ("INFERENCE", "상반기 물량과 EBITDA 마진은 견조했지만 에너지·운송비 상승이 2분기 비용 부담으로 제시됐다. 좋은 실적보다 비용과 건설수요 불확실성이 주가에 더 크게 반영됐다.", "건자재 비용·수요 우려", "S26"),
}


MARKETS = {
    "SPX": {
        "sheet": "US_SPX",
        "label": "미국 · S&P 500",
        "short": "미국",
        "summary": "바이오 임상 이벤트와 엔터프라이즈 소프트웨어가 상승을 주도했다. 반대로 캘리포니아 유틸리티는 법안 리스크, AI 하드웨어·데이터센터 인프라는 장기금리와 혼잡도 완화로 급락했다.",
        "theme": "AI 내부에서 하드웨어 → 소프트웨어로 로테이션",
    },
    "SHSZ300": {
        "sheet": "China_CSI300",
        "label": "중국 · CSI 300",
        "short": "중국",
        "summary": "AI 콘텐츠와 데이터센터 냉각, 금·금융·헬스케어가 상승했다. 반도체 장비와 태양광·풍력·전력기기는 하위권에 집중돼 상류 기술·신재생 장비의 기대치 조정이 뚜렷했다.",
        "theme": "상류 반도체·신재생 장비 → AI 응용·가치·방어",
    },
    "SXXP": {
        "sheet": "Europe_STOXX600",
        "label": "유럽 · STOXX Europe 600",
        "short": "유럽",
        "summary": "금광·광산장비·비료와 실적이 확인된 방어적 성장주가 상위권을 차지했다. 반면 하위 10개 중 방산이 6개, 반도체 장비가 2개로 기존 주도주의 혼잡도 완화가 지수 전반으로 선명하게 드러났다.",
        "theme": "실적형 실물자산·방어주 강세 vs 방산·AI 장비 디레이팅",
    },
}


def clean_ticker(ticker):
    return ticker.replace(" Equity", "")


def dominant_groups(items, n=2):
    counts = Counter(item.get("GICS_Sector") or "미분류" for item in items)
    return ", ".join(f"{name} {count}개" for name, count in counts.most_common(n)) or "자료 없음"


def refresh_market_summaries(data):
    for key, meta in MARKETS.items():
        top_text = dominant_groups(data[key]["top"])
        bottom_text = dominant_groups(data[key]["bottom"])
        meta["theme"] = f"상위: {top_text} · 하위: {bottom_text}"
        meta["summary"] = (
            f"최신 유효 거래일 {data[key]['latest']}까지의 최근 10거래일 기준이다. "
            f"상위 10개는 {top_text}, 하위 10개는 {bottom_text} 비중이 두드러졌다. "
            "성과 원인은 가격·섹터 분포에서 자동 집계했으며 기업별 최신 촉매는 별도 검증이 필요하다."
        )


def has_historical_reason_window(block):
    return (block.get("start"), block.get("latest")) in HISTORICAL_REASON_WINDOWS.values()


def collect_rows(block):
    rows = []
    for direction, key in [("BEST", "top"), ("WORST", "bottom")]:
        for rank, item in enumerate(block[key], 1):
            saved = REASONS.get(item["Ticker"]) if has_historical_reason_window(block) else None
            if saved:
                reason_type, reason, theme, src = saved
            else:
                reason_type = "DATA"
                direction_ko = "상위" if direction == "BEST" else "하위"
                reason = (
                    f"{block['latest']} 기준 최근 10거래일 수익률 {direction_ko} 종목이다. "
                    "순위는 BQuant 가격으로 자동 계산됐으며 최신 공시·뉴스 기반 촉매 설명은 아직 검증하지 않았다."
                )
                theme = f"{item.get('GICS_Sector') or '미분류'} · 가격 {direction_ko}"
                src = ""
            rows.append({
                "rank": rank,
                "direction": direction,
                "ticker": clean_ticker(item["Ticker"]),
                "name": item["Security_Name"],
                "sector": item["GICS_Sector"],
                "industry": item["GICS_Industry_Group"],
                "start_price": item["Price_start"],
                "end_price": item["Price"],
                "return": item["Return_10D"],
                "reason_type": reason_type,
                "reason": reason,
                "theme": theme,
                "source": src,
            })
    return rows


def period_description(data):
    return "; ".join(
        f"{MARKETS[key]['short']} {data[key]['start']}→{data[key]['latest']}"
        for key in MARKETS
    )


def used_source_codes(data):
    codes = set()
    for key in MARKETS:
        for row in collect_rows(data[key]):
            codes.update(code for code in row["source"].split(",") if code)
    return [code for code in SOURCES if code in codes]


def set_default_font(workbook):
    workbook.formats[0].set_font_name("Arial")
    workbook.formats[0].set_font_size(10)


def make_charts(data):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    for key, meta in MARKETS.items():
        rows = collect_rows(data[key])
        top = rows[:10]
        bottom = rows[10:]
        fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.2))
        for ax, subset, title, color in [
            (axes[0], top[::-1], "Best 10", "#2F6BDE"),
            (axes[1], bottom, "Worst 10", "#D84A4A"),
        ]:
            names = [f"{r['ticker'].split()[0]} · {r['name'][:22]}" for r in subset]
            vals = [r["return"] * 100 for r in subset]
            bars = ax.barh(names, vals, color=color, alpha=0.92)
            ax.axvline(0, color="#1D2A3A", linewidth=0.8)
            ax.grid(axis="x", color="#DCE3EC", linewidth=0.7)
            ax.set_title(title, fontsize=14, fontweight="bold", loc="left")
            ax.set_xlabel("10거래일 주가수익률 (%)")
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.tick_params(axis="y", labelsize=9)
            for bar, val in zip(bars, vals):
                if val >= 0:
                    ax.text(val + max(abs(v) for v in vals) * 0.02, bar.get_y() + bar.get_height()/2, f"+{val:.1f}%", va="center", fontsize=9, fontweight="bold")
                else:
                    ax.text(val + max(abs(v) for v in vals) * 0.025, bar.get_y() + bar.get_height()/2, f"{val:.1f}%", va="center", ha="left", fontsize=9, fontweight="bold", color="white")
        fig.suptitle(f"{meta['label']} · 최근 10거래일 상·하위 종목", fontsize=18, fontweight="bold", color="#102A43")
        fig.text(0.01, 0.02, f"기간: {data[key]['start']} → {data[key]['latest']} · 배당 미포함 현지통화 가격수익률 · BQuant", fontsize=9, color="#62748A")
        fig.tight_layout(rect=[0, 0.07, 1, 0.93], w_pad=3.0)
        out = CHART_DIR / f"{key}_10d_rankings.png"
        fig.savefig(out, dpi=180, facecolor="white")
        plt.close(fig)


def build_workbook(data):
    workbook = xlsxwriter.Workbook(XLSX_PATH)
    set_default_font(workbook)
    workbook.set_properties({
        "title": "S&P 500·CSI 300·STOXX Europe 600 최근 10거래일 상·하위 종목",
        "subject": "BQuant 주가수익률 및 촉매·테마 분석",
        "author": "OpenAI Codex",
        "comments": "Returns are simple local-currency price returns, excluding dividends.",
    })

    navy = "#102A43"
    blue = "#2F6BDE"
    teal = "#0FA3A3"
    red = "#D84A4A"
    light = "#F3F6FA"
    grey = "#62748A"
    gold = "#EAAA00"

    title_fmt = workbook.add_format({"font_name": "Arial", "font_size": 22, "bold": True, "font_color": navy, "align": "left", "valign": "vcenter"})
    subtitle_fmt = workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": grey, "text_wrap": True, "valign": "top"})
    section_fmt = workbook.add_format({"font_name": "Arial", "font_size": 13, "bold": True, "font_color": "#FFFFFF", "bg_color": navy, "align": "left", "valign": "vcenter"})
    card_title = workbook.add_format({"font_name": "Arial", "font_size": 12, "bold": True, "font_color": blue, "text_wrap": True, "valign": "top"})
    card_text = workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": navy, "text_wrap": True, "valign": "top", "bg_color": "#FFFFFF", "border": 1, "border_color": "#DCE3EC"})
    header_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "font_color": "#FFFFFF", "bg_color": navy, "align": "center", "valign": "vcenter", "border": 1, "border_color": "#FFFFFF"})
    text_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": navy, "text_wrap": True, "valign": "top", "border": 1, "border_color": "#DCE3EC"})
    center_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": navy, "align": "center", "valign": "vcenter", "border": 1, "border_color": "#DCE3EC"})
    price_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": navy, "num_format": "0.00", "align": "right", "border": 1, "border_color": "#DCE3EC"})
    pct_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "num_format": "+0.0%;-0.0%;0.0%", "align": "right", "border": 1, "border_color": "#DCE3EC"})
    fact_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "font_color": "#0B6E4F", "bg_color": "#E8F5EE", "align": "center", "border": 1, "border_color": "#DCE3EC"})
    inf_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "font_color": "#9A6700", "bg_color": "#FFF4D6", "align": "center", "border": 1, "border_color": "#DCE3EC"})
    link_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": blue, "underline": True, "align": "center", "border": 1, "border_color": "#DCE3EC"})
    note_fmt = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": grey, "italic": True, "text_wrap": True, "valign": "top"})

    ws = workbook.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_zoom(85)
    ws.set_column("A:A", 2)
    ws.set_column("B:D", 22)
    ws.set_column("E:G", 22)
    ws.set_column("H:J", 22)
    ws.merge_range("B2:J3", "S&P 500·CSI 300·STOXX 600 최근 10거래일 승자와 패자", title_fmt)
    ws.merge_range("B4:J5", "BQuant 구성종목 가격자료로 실제 거래일을 맞춘 뒤, 종목별 촉매와 섹터·팩터 로테이션을 구분했다. 세 시장 모두 지수 방향보다 기존 주도주의 혼잡도 완화와 실적으로 확인되는 새로운 리더십이 더 중요했다.", subtitle_fmt)
    ws.merge_range("B7:J7", "핵심 해석", section_fmt)
    blocks = [("B9:D14", "미국", MARKETS["SPX"]), ("E9:G14", "중국", MARKETS["SHSZ300"]), ("H9:J14", "유럽", MARKETS["SXXP"])]
    for cell_range, label, meta in blocks:
        start = cell_range.split(":")[0]
        end = cell_range.split(":")[1]
        start_col = xlsxwriter.utility.xl_cell_to_rowcol(start)[1]
        start_row = xlsxwriter.utility.xl_cell_to_rowcol(start)[0]
        end_col = xlsxwriter.utility.xl_cell_to_rowcol(end)[1]
        end_row = xlsxwriter.utility.xl_cell_to_rowcol(end)[0]
        ws.merge_range(start_row, start_col, start_row, end_col, f"{label} · {meta['theme']}", card_title)
        ws.merge_range(start_row + 1, start_col, end_row, end_col, meta["summary"], card_text)
    ws.merge_range("B16:J16", "공통 테마", section_fmt)
    common = (
        "각 시장의 상·하위 10개 종목과 섹터 집중도를 최신 원자료에서 자동 계산했다.\n"
        "기존 [FACT]/[INFERENCE] 설명은 정확히 같은 과거 분석창에서만 재사용한다.\n"
        "새 기준일에는 [DATA]로 표시하며, 기업별 촉매와 로테이션 해석은 최신 공시·뉴스 검증 후 보강해야 한다."
    )
    ws.merge_range("B18:J22", common, card_text)
    ws.merge_range("B24:J24", "읽을 때 주의할 점", section_fmt)
    ws.merge_range("B26:J29", f"자동 선택 기간: {period_description(data)}. 각 지수에서 유효 종목의 10%를 초과해 가격이 변한 행만 실제 거래일로 판정하고, 최신 11개 관측 종가 사이의 10거래일 수익률을 계산했다. 배당을 제외한 현지통화 단순 가격수익률이다. [DATA]는 자동 계산만 완료된 항목이며 최신 촉매 검증 전이다.", card_text)
    ws.freeze_panes(7, 1)
    ws.print_area("B2:J29")
    ws.set_landscape()
    ws.fit_to_pages(1, 1)
    ws.set_margins(0.3, 0.3, 0.4, 0.4)

    for key, meta in MARKETS.items():
        block = data[key]
        rows = collect_rows(block)
        sh = workbook.add_worksheet(meta["sheet"])
        sh.hide_gridlines(2)
        sh.set_zoom(75)
        sh.freeze_panes(7, 0)
        sh.set_column("A:A", 7)
        sh.set_column("B:B", 8)
        sh.set_column("C:C", 15)
        sh.set_column("D:D", 30)
        sh.set_column("E:E", 21)
        sh.set_column("F:F", 31)
        sh.set_column("G:H", 12)
        sh.set_column("I:I", 12)
        sh.set_column("J:J", 12)
        sh.set_column("K:K", 78)
        sh.set_column("L:L", 26)
        sh.set_column("M:M", 13)
        sh.merge_range("A1:M2", f"{meta['label']} · 최근 10거래일 Best / Worst 10", title_fmt)
        sh.merge_range("A3:M4", f"기간: {block['start']} → {block['latest']} | 구성종목 {block['constituents']}개 | 배당 미포함 현지통화 가격수익률 | {meta['summary']}", subtitle_fmt)
        sh.write("A6", "Rank", header_fmt)
        sh.write("B6", "구분", header_fmt)
        sh.write("C6", "Ticker", header_fmt)
        sh.write("D6", "종목명", header_fmt)
        sh.write("E6", "Sector", header_fmt)
        sh.write("F6", "Industry Group", header_fmt)
        sh.write("G6", "시작가", header_fmt)
        sh.write("H6", "종료가", header_fmt)
        sh.write("I6", "10D Return", header_fmt)
        sh.write("J6", "근거", header_fmt)
        sh.write("K6", "성과 요인", header_fmt)
        sh.write("L6", "부각 테마", header_fmt)
        sh.write("M6", "Source", header_fmt)
        for idx, row in enumerate(rows, 6):
            excel_row = idx + 1
            sh.write_number(idx, 0, row["rank"], center_fmt)
            sh.write(idx, 1, row["direction"], center_fmt)
            sh.write(idx, 2, row["ticker"], text_fmt)
            sh.write(idx, 3, row["name"], text_fmt)
            sh.write(idx, 4, row["sector"], text_fmt)
            sh.write(idx, 5, row["industry"], text_fmt)
            sh.write_number(idx, 6, row["start_price"], price_fmt)
            sh.write_number(idx, 7, row["end_price"], price_fmt)
            sh.write_formula(idx, 8, f"=H{excel_row}/G{excel_row}-1", pct_fmt, row["return"])
            sh.write(idx, 9, row["reason_type"], fact_fmt if row["reason_type"] == "FACT" else inf_fmt)
            sh.write(idx, 10, row["reason"], text_fmt)
            sh.write(idx, 11, row["theme"], text_fmt)
            if row["source"]:
                first_src = row["source"].split(",")[0]
                sh.write_url(idx, 12, SOURCES[first_src][1], link_fmt, row["source"])
            else:
                sh.write(idx, 12, "—", center_fmt)
            sh.set_row(idx, 46)
        sh.conditional_format(6, 8, 25, 8, {"type": "3_color_scale", "min_color": "#F5B7B1", "mid_color": "#FFFFFF", "max_color": "#A9DFBF"})
        sh.autofilter(5, 0, 25, 12)
        sh.write("A28", "요약", section_fmt)
        sh.merge_range("B28:M28", meta["theme"], section_fmt)
        sh.merge_range("A30:M33", meta["summary"], card_text)
        sh.merge_range("A35:M37", "[FACT]는 해당 기간의 공시·보도에서 직접 확인된 촉매다. [INFERENCE]는 기업별 신규 뉴스가 없거나 영향이 작아 동종업종 수익률, 금리, 원자재, 포지셔닝을 통해 해석한 것이다. 추론을 실적 악화의 확정 근거로 사용하면 안 된다.", note_fmt)
        sh.set_landscape()
        sh.print_area("A1:M37")
        sh.fit_to_pages(1, 1)
        sh.repeat_rows(0, 5)
        sh.set_margins(0.25, 0.25, 0.4, 0.4)

    meth = workbook.add_worksheet("Methodology")
    meth.hide_gridlines(2)
    meth.set_column("A:A", 3)
    meth.set_column("B:B", 25)
    meth.set_column("C:C", 100)
    meth.merge_range("B2:C3", "방법론과 출처", title_fmt)
    items = [
        ("Universe", "S&P 500, CSI 300, STOXX Europe 600의 BQuant 구성종목. 전체 상장주가 아니라 각 대표지수 내부 순위다."),
        ("기간", f"{period_description(data)}. 입력 데이터에서 지수별 최신 유효 거래일을 자동 탐지한다."),
        ("거래일 판정", "전일과 당일 가격이 모두 유효한 구성종목 중 10%를 초과해 가격이 변한 날짜를 실제 거래일로 판정한다. 휴일·시차로 직전 값이 반복된 행은 자동 제외된다."),
        ("수익률", "현지통화, 배당 미포함. I열은 H열/ G열 - 1의 Excel 수식이며 계산값을 함께 저장했다."),
        ("구성종목", "시작일과 종료일 모두 가격이 존재하는 종목의 교집합. 10거래일의 짧은 구간이므로 구성 변경 편향은 제한적이지만 완전히 제거되지는 않는다."),
        ("근거 등급", "FACT: 공식 공시·기업 발표·신뢰도 높은 보도가 해당 기간 주가 촉매를 직접 설명. INFERENCE: 동종업종·팩터·금리·원자재·포지셔닝에 기반한 해석."),
        ("제약", "10거래일 수익률은 이벤트·숏커버·유동성에 민감하며 장기 이익 추세와 다를 수 있다. 개별 촉매가 확인되지 않은 종목은 원인을 단정하지 않았다."),
    ]
    meth.write("B5", "항목", header_fmt)
    meth.write("C5", "설명", header_fmt)
    for r, (k, v) in enumerate(items, 5):
        meth.write(r, 1, k, text_fmt)
        meth.write(r, 2, v, text_fmt)
        meth.set_row(r, 48)
    meth.write("B14", "Source", header_fmt)
    meth.write("C14", "URL", header_fmt)
    for r, code in enumerate(used_source_codes(data), 14):
        name, url = SOURCES[code]
        meth.write(r, 1, f"{code} · {name}", text_fmt)
        meth.write_url(r, 2, url, link_fmt, url)
        meth.set_row(r, 32)
    meth.print_area("B2:C28")
    meth.set_landscape()
    meth.fit_to_pages(1, 1)
    workbook.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build current Top/Down 10 charts and workbook from the latest rankings JSON."
    )
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main():
    global DATA_PATH, OUT_DIR, XLSX_PATH, ENRICHED_PATH, CHART_DIR
    args = parse_args()
    DATA_PATH = args.data.resolve()
    OUT_DIR = args.output_dir.resolve()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    refresh_market_summaries(data)
    as_of = max(data[key]["latest"] for key in MARKETS)
    tag = as_of.replace("-", "")
    XLSX_PATH = OUT_DIR / f"SPX_CSI300_STOXX600_10D_Top10_Down10_{tag}.xlsx"
    ENRICHED_PATH = OUT_DIR / "Market_10D_Enriched_latest.json"
    CHART_DIR = OUT_DIR / "charts"
    enriched = {
        "meta": {
            "asOf": as_of,
            "tag": tag,
            "rankingData": str(DATA_PATH),
            "workbook": str(XLSX_PATH),
            "chartDir": str(CHART_DIR),
        },
        "markets": {
            key: {
                **MARKETS[key],
                "start": data[key]["start"],
                "latest": data[key]["latest"],
                "constituents": data[key]["constituents"],
                "rows": collect_rows(data[key]),
            }
            for key in MARKETS
        },
        "sources": {
            code: {"name": SOURCES[code][0], "url": SOURCES[code][1]}
            for code in used_source_codes(data)
        },
    }
    payload = json.dumps(enriched, ensure_ascii=False, indent=2)
    ENRICHED_PATH.write_text(payload, encoding="utf-8")
    dated_enriched = OUT_DIR / f"Market_10D_Enriched_{tag}.json"
    dated_enriched.write_text(payload, encoding="utf-8")
    make_charts(data)
    build_workbook(data)
    latest_outputs = {
        "asOf": as_of,
        "tag": tag,
        "rankings": str(DATA_PATH),
        "enriched": str(ENRICHED_PATH),
        "datedEnriched": str(dated_enriched),
        "workbook": str(XLSX_PATH),
        "chartDir": str(CHART_DIR),
        "docx": str(OUT_DIR / f"SPX_CSI300_STOXX600_최근10거래일_Top10_Down10_{tag}.docx"),
        "pdf": str(OUT_DIR / f"SPX_CSI300_STOXX600_최근10거래일_Top10_Down10_{tag}_preview.pdf"),
    }
    (OUT_DIR / "latest_outputs.json").write_text(
        json.dumps(latest_outputs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(XLSX_PATH)
    print(ENRICHED_PATH)
    print(OUT_DIR / "latest_outputs.json")
    for path in sorted(CHART_DIR.glob("*.png")):
        print(path)


if __name__ == "__main__":
    main()
````

## build_market_10d_report.js

latest JSON을 읽고 동적 파일명으로 Word 보고서 생성.

````javascript
const fs = require('fs');
const path = require('path');
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  HeadingLevel,
  ImageRun,
  PageBreak,
  PageNumber,
  PageOrientation,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require('docx');

const dataPath = process.argv[2] || path.join(__dirname, 'output', 'Market_10D_Enriched_latest.json');
const chartDir = path.join(__dirname, 'output', 'charts');
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const tag = data.meta?.tag || String(data.meta?.asOf || '').replaceAll('-', '');
const outPath = process.argv[3] || path.join(__dirname, 'output', `SPX_CSI300_STOXX600_최근10거래일_Top10_Down10_${tag}.docx`);

const C = {
  navy: '102A43', blue: '2F6BDE', teal: '0FA3A3', red: 'D84A4A', gray: '62748A',
  light: 'F3F6FA', white: 'FFFFFF', green: '0B6E4F', greenLight: 'E8F5EE',
  amber: '9A6700', amberLight: 'FFF4D6', border: 'DCE3EC', black: '172B4D'
};

function run(text, opts = {}) {
  return new TextRun({ text, font: opts.font || 'Malgun Gothic', size: opts.size || 19,
    bold: opts.bold, italics: opts.italics, color: opts.color || C.navy });
}

function p(text, opts = {}) {
  const children = [];
  const tag = text.match(/^\[(DATA|FACT|INFERENCE|RISK|OPEN QUESTION)\]\s*/);
  if (tag) {
    const label = `[${tag[1]}] `;
    const color = tag[1] === 'FACT' ? C.green : tag[1] === 'INFERENCE' ? C.blue : tag[1] === 'DATA' ? C.teal : C.amber;
    children.push(run(label, { bold: true, color, size: opts.size || 18 }));
    children.push(run(text.slice(tag[0].length), { size: opts.size || 18, color: opts.color || C.navy }));
  } else {
    children.push(run(text, { size: opts.size || 18, bold: opts.bold, color: opts.color || C.navy, italics: opts.italics }));
  }
  return new Paragraph({
    children,
    bullet: opts.bullet ? { level: 0 } : undefined,
    alignment: opts.alignment,
    spacing: { before: opts.before || 0, after: opts.after ?? 95, line: opts.line || 270 },
    keepNext: opts.keepNext,
  });
}

function heading(text, level = 1) {
  const levelMap = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3 };
  const colors = { 1: C.navy, 2: C.blue, 3: C.teal };
  return new Paragraph({
    heading: levelMap[level],
    children: [run(text, { bold: true, color: colors[level], size: level === 1 ? 32 : level === 2 ? 25 : 21 })],
    spacing: { before: level === 1 ? 220 : 150, after: 110 },
    keepNext: true,
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function borders(color = C.border) {
  return {
    top: { style: BorderStyle.SINGLE, size: 3, color },
    bottom: { style: BorderStyle.SINGLE, size: 3, color },
    left: { style: BorderStyle.SINGLE, size: 3, color },
    right: { style: BorderStyle.SINGLE, size: 3, color },
  };
}

function cell(text, width, opts = {}) {
  const children = opts.children || [new Paragraph({
    children: [run(text, { size: opts.size || 15, bold: opts.bold, color: opts.color || C.navy })],
    alignment: opts.alignment,
    spacing: { after: 0, line: 210 },
  })];
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 65, bottom: 65, left: 75, right: 75 },
    borders: borders(),
    verticalAlign: 'center',
    children,
  });
}

function evidenceCell(type, width) {
  const fact = type === 'FACT';
  return cell(type, width, {
    size: 14, bold: true, alignment: AlignmentType.CENTER,
    color: fact ? C.green : C.amber,
    fill: fact ? C.greenLight : C.amberLight,
  });
}

function rankTable(rows, title, positive) {
  const widths = [650, 3200, 1150, 1250, 8700];
  const header = new TableRow({
    tableHeader: true,
    children: ['순위', '종목 / 섹터', '10D', '근거', '성과 요인 / 부각 테마'].map((t, i) => cell(t, widths[i], {
      fill: C.navy, color: C.white, bold: true, size: 15, alignment: AlignmentType.CENTER,
    }))
  });
  const body = rows.map((r, idx) => {
    const nameBlock = [
      new Paragraph({ children: [run(`${r.ticker} · ${r.name}`, { size: 15, bold: true })], spacing: { after: 35, line: 205 } }),
      new Paragraph({ children: [run(`${r.sector} / ${r.industry}`, { size: 13, color: C.gray })], spacing: { after: 0, line: 190 } }),
    ];
    const reasonBlock = [
      new Paragraph({ children: [run(r.theme, { size: 14, bold: true, color: positive ? C.blue : C.red })], spacing: { after: 35, line: 200 } }),
      new Paragraph({ children: [run(r.reason, { size: 14 })], spacing: { after: 0, line: 215 } }),
    ];
    return new TableRow({
      cantSplit: true,
      children: [
        cell(String(r.rank), widths[0], { alignment: AlignmentType.CENTER, size: 15, bold: true, fill: idx % 2 ? C.light : C.white }),
        cell('', widths[1], { children: nameBlock, fill: idx % 2 ? C.light : C.white }),
        cell(`${r.return >= 0 ? '+' : ''}${(r.return * 100).toFixed(1)}%`, widths[2], { alignment: AlignmentType.CENTER, size: 15, bold: true, color: positive ? C.blue : C.red, fill: idx % 2 ? C.light : C.white }),
        evidenceCell(r.reason_type, widths[3]),
        cell('', widths[4], { children: reasonBlock, fill: idx % 2 ? C.light : C.white }),
      ],
    });
  });
  return [
    heading(title, 2),
    new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths, rows: [header, ...body] }),
  ];
}

function marketSection(key) {
  const m = data.markets[key];
  const top = m.rows.filter(r => r.direction === 'BEST');
  const bottom = m.rows.filter(r => r.direction === 'WORST');
  const chartPath = path.join(chartDir, `${key}_10d_rankings.png`);
  const imgWidth = 880;
  const imgHeight = Math.round(imgWidth * 1116 / 2430);
  const factTop = top.filter(r => r.reason_type === 'FACT').length;
  const factBottom = bottom.filter(r => r.reason_type === 'FACT').length;
  return [
    pageBreak(),
    heading(m.label, 1),
    p(`${m.start} → ${m.latest} · ${m.constituents}개 구성종목 · 배당 미포함 현지통화 가격수익률`, { color: C.gray, size: 17 }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ data: fs.readFileSync(chartPath), transformation: { width: imgWidth, height: imgHeight }, type: 'png' })], spacing: { before: 70, after: 90 } }),
    p(`[DATA] ${m.summary}`, { size: 18 }),
    p(`[DATA] 현재 분석창에서 직접 확인된 과거 기업별 촉매가 연결된 항목은 상위 ${factTop}개, 하위 ${factBottom}개다. [DATA] 항목은 가격 순위만 자동 갱신된 것이므로 최신 공시·뉴스를 확인하기 전에는 원인을 단정하지 않는다.`, { size: 17 }),
    pageBreak(),
    ...rankTable(top, `${m.short} Best 10`, true),
    pageBreak(),
    ...rankTable(bottom, `${m.short} Worst 10`, false),
  ];
}

function sourceParagraph(code, src) {
  return new Paragraph({
    children: [
      run(`${code} · ${src.name}: `, { size: 16, bold: true }),
      new ExternalHyperlink({ link: src.url, children: [run(src.url, { size: 16, color: C.blue })] }),
    ],
    spacing: { after: 80, line: 240 },
  });
}

const marketKeys = Object.keys(data.markets);
const periodText = marketKeys
  .map(key => `${data.markets[key].short} ${data.markets[key].start}→${data.markets[key].latest}`)
  .join(' · ');

const body = [
  new Paragraph({ children: [run('S&P 500·CSI 300·STOXX Europe 600', { size: 42, bold: true, color: C.navy })], spacing: { after: 80 } }),
  new Paragraph({ children: [run('최근 10거래일 Best / Worst 10', { size: 36, bold: true, color: C.blue })], spacing: { after: 170 } }),
  p('최신 BQuant 가격으로 자동 갱신되는 시장 내부 로테이션 모니터', { size: 24, color: C.gray, after: 280 }),
  p(`기준일 ${data.meta.asOf} · ${periodText} · 배당 미포함 현지통화 가격수익률`, { size: 18, color: C.gray }),
  pageBreak(),

  heading('Executive Summary', 1),
  p(`[DATA] 입력 파일에서 지수별 최신 유효 거래일을 찾고, 직전 값 반복일과 휴일을 제외한 최근 11개 종가 사이의 10거래일 수익률로 순위를 계산했다. ${periodText}.`),
  ...marketKeys.map(key => p(`[DATA] ${data.markets[key].label}: ${data.markets[key].summary}`)),
  p('[RISK] 순위와 섹터 집중도는 자동 갱신되지만 기업별 촉매는 자동 확정하지 않는다. [DATA]로 표시된 종목은 최신 공시·뉴스를 별도로 확인해야 한다.'),

  ...marketKeys.flatMap(key => marketSection(key)),

  pageBreak(),
  heading('Cross-market Read', 1),
  ...marketKeys.map(key => {
    const m = data.markets[key];
    return p(`[DATA] ${m.label} · ${m.theme}`);
  }),
  p('[INFERENCE] 여러 시장에서 같은 섹터가 동시에 상위 또는 하위에 집중될 때 공통 팩터 로테이션일 가능성이 높다. 단일 시장·단일 종목 움직임은 기업 이벤트 가능성을 우선 점검한다.'),
  p('[RISK] 10거래일은 이벤트, 숏커버, 유동성에 민감하다. 상위 종목을 구조적 승자로, 하위 종목을 펀더멘털 훼손으로 곧바로 해석하지 않는다.'),

  heading('Methodology', 1),
  p('[DATA] Universe는 S&P 500, CSI 300, STOXX Europe 600의 최신 BQuant 구성종목이다. 전체 상장주 순위가 아니다.'),
  p('[DATA] 전일과 당일 가격이 모두 유효한 구성종목 중 10%를 초과해 가격이 변한 날짜를 실제 거래일로 판정한다. 각 지수의 마지막 유효 거래일에서 10개 거래구간 전 종가를 시작값으로 쓴다.'),
  p('[DATA] 시작일과 종료일 가격이 모두 존재하고 시작가격이 양수인 종목만 포함한다. 수익률은 현지통화 단순 가격수익률이며 배당과 환율효과를 포함하지 않는다.'),
  p('[DATA] [FACT]와 [INFERENCE] 설명은 해당 분석창과 정확히 일치할 때만 과거 검증자료를 연결한다. 새로운 분석창은 [DATA] 상태로 생성되어 촉매 검증이 필요하다.'),

  heading('Next Checks', 1),
  p('[OPEN QUESTION] 상·하위 종목의 최신 실적 발표, 가이던스, 규제·정책, M&A, 자본조달 공시가 가격 변화를 직접 설명하는가?'),
  p('[OPEN QUESTION] 같은 섹터 종목이 여러 시장에서 함께 움직였는가, 아니면 한 시장의 특수 이벤트인가?'),
  p('[OPEN QUESTION] 10거래일 수익률이 EPS 추정치 변화와 동행하는가, 아니면 P/E·포지셔닝 변화가 주도했는가?'),

  pageBreak(),
  heading('Sources', 1),
  p('가격·구성종목: 사용자 제공 BQuant 원자료. 기업별 촉매를 검증한 분석창에서는 아래 출처가 함께 표시된다.', { color: C.gray }),
  ...(Object.keys(data.sources).length
    ? Object.entries(data.sources).map(([code, src]) => sourceParagraph(code, src))
    : [p('[DATA] 이번 자동 갱신본에는 최신 기업별 촉매 출처가 아직 연결되지 않았다.', { color: C.gray })]),
];

const doc = new Document({
  creator: 'OpenAI Codex',
  title: 'S&P 500·CSI 300·STOXX Europe 600 최근 10거래일 Top10·Down10 분석',
  description: 'BQuant 가격자료와 기업 공시·시장 보도를 결합한 최근 10거래일 성과 요인 분석',
  styles: {
    default: { document: { run: { font: 'Malgun Gothic', size: 19, color: C.navy }, paragraph: { spacing: { line: 270 } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Malgun Gothic', size: 32, bold: true, color: C.navy },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Malgun Gothic', size: 25, bold: true, color: C.blue },
        paragraph: { spacing: { before: 170, after: 100 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Malgun Gothic', size: 21, bold: true, color: C.teal },
        paragraph: { spacing: { before: 140, after: 90 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE },
        margin: { top: 650, right: 650, bottom: 650, left: 650 },
      },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        run('10D Market Leaders & Laggards  |  ', { size: 14, color: C.gray, font: 'Aptos' }),
        new TextRun({ children: [PageNumber.CURRENT], size: 14, color: C.gray, font: 'Aptos' }),
      ] })] }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log(outPath);
});
````

## validate_market_10d_workbook.py

latest_outputs.json이 가리키는 Excel 검증.

````python
import argparse
import json
from pathlib import Path

from openpyxl import load_workbook


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "output" / "latest_outputs.json"
expected = {"Summary", "US_SPX", "China_CSI300", "Europe_STOXX600", "Methodology"}


def default_path():
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Run build_market_10d_outputs.py first: {MANIFEST}")
    metadata = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return Path(metadata["workbook"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", nargs="?", type=Path)
    args = parser.parse_args()
    path = (args.workbook or default_path()).resolve()

    wb_formula = load_workbook(path, data_only=False, read_only=False)
    wb_values = load_workbook(path, data_only=True, read_only=True)
    assert set(wb_formula.sheetnames) == expected, wb_formula.sheetnames

    formula_count = 0
    errors = []
    for ws in wb_formula.worksheets:
        values_ws = wb_values[ws.title]
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    formula_count += 1
                    cached = values_ws[cell.coordinate].value
                    if isinstance(cached, str) and cached.startswith("#"):
                        errors.append((ws.title, cell.coordinate, cached))

    for sheet in ["US_SPX", "China_CSI300", "Europe_STOXX600"]:
        ws = wb_formula[sheet]
        assert ws.max_row >= 37
        assert ws["I7"].data_type == "f"
        assert ws["I26"].data_type == "f"
        values = wb_values[sheet]
        for row in range(7, 27):
            expected_return = values[f"H{row}"].value / values[f"G{row}"].value - 1
            assert abs(values[f"I{row}"].value - expected_return) < 1e-10

    assert formula_count == 60, formula_count
    assert not errors, errors
    print(f"sheets={wb_formula.sheetnames}")
    print(f"formulas={formula_count}")
    print("formula_errors=0")
    print(path)


if __name__ == "__main__":
    main()
````

## render_market_10d_report.py

latest_outputs.json이 가리키는 PDF 렌더링.

````python
import json
from pathlib import Path
import sys

import pypdfium2 as pdfium
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "output" / "latest_outputs.json"


def default_pdf():
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Run build_market_10d_outputs.py first: {MANIFEST}")
    return Path(json.loads(MANIFEST.read_text(encoding="utf-8"))["pdf"])


PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else default_pdf()
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else PDF.parent
OUT.mkdir(parents=True, exist_ok=True)

pdf = pdfium.PdfDocument(str(PDF))
thumbs = []
for index in range(len(pdf)):
    image = pdf[index].render(scale=1.2).to_pil().convert("RGB")
    image.save(OUT / f"page-{index + 1:02d}.png")
    thumb = image.copy()
    thumb.thumbnail((420, 300))
    card = Image.new("RGB", (440, 335), "white")
    card.paste(thumb, ((440 - thumb.width) // 2, 10))
    ImageDraw.Draw(card).text((12, 312), f"p.{index + 1}", fill="#102A43")
    thumbs.append(card)

cols = 2
per_sheet = 8
for sheet_index, start in enumerate(range(0, len(thumbs), per_sheet), 1):
    batch = thumbs[start:start + per_sheet]
    rows = (len(batch) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 440, rows * 335), "#DCE3EC")
    for idx, thumb in enumerate(batch):
        sheet.paste(thumb, ((idx % cols) * 440, (idx // cols) * 335))
    sheet.save(OUT / f"contact-sheet-{sheet_index:02d}.png")

print(f"pages={len(pdf)}")
print(OUT)
````

## run_top10_update.ps1

계산부터 검증까지 한 번에 실행.

````powershell
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SourceFiles
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$bundledNodeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node'
$bundledNode = Join-Path $bundledNodeRoot 'bin\node.exe'
$bundledNodeModules = Join-Path $bundledNodeRoot 'node_modules'

$nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } elseif (Test-Path -LiteralPath $bundledNode) { $bundledNode } else { $null }
if (Test-Path -LiteralPath $bundledNodeModules) {
    $env:NODE_PATH = $bundledNodeModules
}

if (-not $pythonCommand) {
    throw 'Python을 찾지 못했습니다. Python 3와 numpy, matplotlib, xlsxwriter, openpyxl을 설치하세요.'
}

& $pythonCommand.Source (Join-Path $scriptDir 'compute_10d_rankings.py') @SourceFiles
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 calculation failed with exit code $LASTEXITCODE"
}

& $pythonCommand.Source (Join-Path $scriptDir 'build_market_10d_outputs.py')
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 workbook build failed with exit code $LASTEXITCODE"
}

if ($nodeExecutable) {
    & $nodeExecutable (Join-Path $scriptDir 'build_market_10d_report.js')
    if ($LASTEXITCODE -ne 0) {
        throw "Top10/Down10 Word report build failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Warning 'Node.js를 찾지 못해 Word 보고서는 건너뛰었습니다. JSON, 차트, Excel은 생성됐습니다.'
}

& $pythonCommand.Source (Join-Path $scriptDir 'validate_market_10d_workbook.py')
if ($LASTEXITCODE -ne 0) {
    throw "Top10/Down10 workbook validation failed with exit code $LASTEXITCODE"
}

$latestManifest = Join-Path $scriptDir 'output\latest_outputs.json'
Write-Host "완료: $latestManifest"
````

