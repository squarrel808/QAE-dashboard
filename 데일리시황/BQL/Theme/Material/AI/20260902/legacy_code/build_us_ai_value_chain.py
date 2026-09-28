from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xlsxwriter


OUT_DIR = Path(r"C:\Users\USER\Downloads\유로존")
OUT_XLSX = OUT_DIR / "US_AI_Value_Chain_3M_Rotation_20260901.xlsx"
OUT_LINE = OUT_DIR / "US_AI_Value_Chain_3M_Normalized_20260901.png"
OUT_BAR = OUT_DIR / "US_AI_Value_Chain_3M_Return_20260901.png"
OUT_HEAT = OUT_DIR / "US_AI_Value_Chain_Monthly_Rotation_20260901.png"
START = pd.Timestamp("2026-06-01")
END = pd.Timestamp("2026-08-31")


BASKETS = OrderedDict(
    {
        "하이퍼스케일러·플랫폼": ["MSFT", "AMZN", "GOOGL", "META", "ORCL"],
        "AI 연산·메모리": ["NVDA", "AMD", "AVGO", "MRVL", "MU"],
        "파운드리·반도체 장비": ["TSM", "ASML", "AMAT", "LRCX", "KLAC"],
        "네트워크·광통신": ["ANET", "CSCO", "CIEN", "COHR", "LITE"],
        "서버·스토리지": ["DELL", "HPE", "SMCI", "NTAP"],
        "전력·냉각 장비": ["VRT", "ETN", "GEV", "CARR", "TT"],
        "E&C·설치": ["PWR", "EME", "FIX", "MTZ", "ACM"],
        "데이터센터 REIT": ["EQIX", "DLR", "IRM"],
        "전력 생산": ["CEG", "VST", "NRG", "TLN"],
        "사이버보안": ["PANW", "CRWD", "FTNT", "ZS", "NET"],
        "AI 소프트웨어·데이터": ["PLTR", "NOW", "SNOW", "DDOG", "MDB", "CRM"],
    }
)

DESCRIPTIONS = {
    "하이퍼스케일러·플랫폼": "클라우드·모델·AI 서비스 수요를 만들고 대규모 데이터센터 CAPEX를 집행하는 최종 수요자",
    "AI 연산·메모리": "GPU·가속기·커스텀 실리콘·HBM 등 AI 서버의 핵심 반도체",
    "파운드리·반도체 장비": "첨단 칩을 생산·패키징하기 위한 파운드리와 전공정 장비",
    "네트워크·광통신": "AI 클러스터 내부와 데이터센터 간 대역폭을 연결하는 스위치·라우터·광부품",
    "서버·스토리지": "가속기를 탑재하고 데이터를 저장하는 서버·랙·스토리지 시스템",
    "전력·냉각 장비": "UPS·배전·열관리·냉각 등 데이터센터 전력 밀도를 처리하는 장비",
    "E&C·설치": "변전·전기·기계설비와 데이터센터를 실제로 설계·시공·연결하는 사업자",
    "데이터센터 REIT": "전력과 연결성을 갖춘 데이터센터 공간을 개발·임대하는 자산 소유자",
    "전력 생산": "데이터센터의 장기 전력 수요 증가를 판매량·계약가격으로 흡수하는 발전사",
    "사이버보안": "클라우드·AI 워크로드와 에이전트 확산에 따라 늘어나는 공격면을 보호",
    "AI 소프트웨어·데이터": "기업 데이터·업무흐름에 AI를 적용해 사용량·구독 매출로 수익화",
}


def fetch_yahoo(ticker: str) -> pd.Series:
    p1 = int((START - pd.Timedelta(days=7)).timestamp())
    p2 = int((END + pd.Timedelta(days=2)).timestamp())
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(ticker)
        + f"?period1={p1}&period2={p2}&interval=1d&events=history"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            result = data["chart"]["result"][0]
            ts = result["timestamp"]
            close = result["indicators"]["quote"][0]["close"]
            dates = [datetime.fromtimestamp(x, tz=timezone.utc).date() for x in ts]
            s = pd.Series(close, index=pd.to_datetime(dates), name=ticker, dtype=float)
            s = s[~s.index.duplicated(keep="last")].sort_index()
            s = s.loc[(s.index >= START) & (s.index <= END)].dropna()
            if len(s) < 50:
                raise RuntimeError(f"insufficient observations: {len(s)}")
            return s
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Yahoo download failed for {ticker}: {last_error}")


def pct(v: float) -> str:
    return f"{v:+.1%}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_tickers = list(dict.fromkeys(t for names in BASKETS.values() for t in names))
    series = {}
    failures = []
    for ticker in all_tickers + ["SPY", "QQQ"]:
        try:
            series[ticker] = fetch_yahoo(ticker)
            print(ticker, len(series[ticker]), series[ticker].index.min().date(), series[ticker].index.max().date())
        except Exception as exc:
            failures.append((ticker, str(exc)))
            print("FAILED", ticker, exc)
    if failures:
        raise RuntimeError(f"download failures: {failures}")

    prices = pd.concat(series.values(), axis=1).sort_index().ffill()
    prices = prices.loc[(prices.index >= START) & (prices.index <= END)]
    prices = prices.dropna(how="any")
    normalized = prices.div(prices.iloc[0]).mul(100)

    basket_idx = pd.DataFrame(index=normalized.index)
    for basket, tickers in BASKETS.items():
        basket_idx[basket] = normalized[tickers].mean(axis=1)
    basket_idx["SPY"] = normalized["SPY"]
    basket_idx["QQQ"] = normalized["QQQ"]

    month_ends = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-07-31"), pd.Timestamp("2026-08-31")]
    monthly = pd.DataFrame(index=list(BASKETS.keys()) + ["SPY", "QQQ"], columns=["6월", "7월", "8월"], dtype=float)
    for name in monthly.index:
        s = basket_idx[name]
        june_start = s.iloc[0]
        june_end = s.loc[:month_ends[0]].iloc[-1]
        july_start = s.loc[:month_ends[0]].iloc[-1]
        july_end = s.loc[:month_ends[1]].iloc[-1]
        aug_start = s.loc[:month_ends[1]].iloc[-1]
        aug_end = s.loc[:month_ends[2]].iloc[-1]
        monthly.loc[name] = [june_end / june_start - 1, july_end / july_start - 1, aug_end / aug_start - 1]

    rows = []
    one_m_start = basket_idx.loc[:pd.Timestamp("2026-07-31")].iloc[-1]
    for name in list(BASKETS.keys()) + ["SPY", "QQQ"]:
        s = basket_idx[name]
        three_m = s.iloc[-1] / s.iloc[0] - 1
        one_m = s.iloc[-1] / one_m_start[name] - 1
        drawdown = (s / s.cummax() - 1).min()
        rows.append(
            {
                "밸류체인": name,
                "구성 종목": ", ".join(BASKETS.get(name, [name])),
                "종목 수": len(BASKETS.get(name, [name])),
                "3개월 수익률": three_m,
                "최근 1개월 수익률": one_m,
                "3개월 최대낙폭": drawdown,
                "SPY 대비 3개월": three_m - (basket_idx["SPY"].iloc[-1] / basket_idx["SPY"].iloc[0] - 1),
            }
        )
    summary = pd.DataFrame(rows).sort_values("3개월 수익률", ascending=False).reset_index(drop=True)

    # Visuals
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    colors = plt.cm.tab20(np.linspace(0, 1, len(BASKETS)))

    fig, ax = plt.subplots(figsize=(15, 8.5))
    for i, name in enumerate(BASKETS):
        ax.plot(basket_idx.index, basket_idx[name], lw=2.0, label=name, color=colors[i])
    ax.plot(basket_idx.index, basket_idx["SPY"], color="#111827", lw=2.5, ls="--", label="SPY")
    ax.axhline(100, color="#9ca3af", lw=0.8)
    ax.set_title("미국 AI 밸류체인 동일가중 지수 (2026-06-01=100)", fontsize=18, fontweight="bold", loc="left")
    ax.set_ylabel("지수")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=3, fontsize=9, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT_LINE, dpi=180, bbox_inches="tight")
    plt.close(fig)

    bar_data = summary[~summary["밸류체인"].isin(["SPY", "QQQ"])].sort_values("3개월 수익률")
    fig, ax = plt.subplots(figsize=(12.5, 7.5))
    bar_colors = ["#dc2626" if x < 0 else "#2563eb" for x in bar_data["3개월 수익률"]]
    bars = ax.barh(bar_data["밸류체인"], bar_data["3개월 수익률"] * 100, color=bar_colors)
    for b, v in zip(bars, bar_data["3개월 수익률"]):
        ax.text(v * 100 + (0.5 if v >= 0 else -0.5), b.get_y() + b.get_height() / 2, f"{v:+.1%}", va="center", ha="left" if v >= 0 else "right", fontweight="bold")
    ax.axvline(0, color="#111827", lw=0.8)
    ax.set_title("최근 3개월 AI 밸류체인 수익률", fontsize=18, fontweight="bold", loc="left")
    ax.set_xlabel("수익률 (%)")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_BAR, dpi=180, bbox_inches="tight")
    plt.close(fig)

    heat = monthly.loc[list(BASKETS.keys())].astype(float) * 100
    fig, ax = plt.subplots(figsize=(9, 8.2))
    vmax = max(abs(heat.min().min()), abs(heat.max().max()))
    im = ax.imshow(heat.values, cmap="RdYlBu", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(heat.columns)), heat.columns)
    ax.set_yticks(range(len(heat.index)), heat.index)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat.iat[i,j]:+.1f}%", ha="center", va="center", fontsize=10, fontweight="bold")
    ax.set_title("월별 로테이션: 동일가중 밸류체인 수익률", fontsize=17, fontweight="bold", loc="left")
    fig.colorbar(im, ax=ax, shrink=0.8, label="월간 수익률 (%)")
    fig.tight_layout()
    fig.savefig(OUT_HEAT, dpi=180, bbox_inches="tight")
    plt.close(fig)

    # Workbook
    wb = xlsxwriter.Workbook(OUT_XLSX)
    wb.set_properties(
        {
            "title": "US AI Value Chain 3M Rotation",
            "subject": "Equal-weight price return analysis",
            "author": "OpenAI Codex",
            "comments": "Yahoo Finance daily unadjusted closes; no dividends; equal-weight basket index.",
        }
    )
    navy = "#0B2A4A"
    blue = "#2F6BDE"
    teal = "#09A7A9"
    gray = "#5F6B7A"
    light = "#F3F6FA"
    white = "#FFFFFF"
    red = "#D94B4B"
    title_fmt = wb.add_format({"font_name": "Aptos", "font_size": 20, "bold": True, "font_color": navy})
    subtitle_fmt = wb.add_format({"font_name": "Aptos", "font_size": 10, "font_color": gray})
    header_fmt = wb.add_format({"font_name": "Aptos", "bold": True, "font_color": white, "bg_color": navy, "border": 0, "align": "center", "valign": "vcenter"})
    text_fmt = wb.add_format({"font_name": "Aptos", "font_size": 10, "font_color": navy, "valign": "top"})
    wrap_fmt = wb.add_format({"font_name": "Aptos", "font_size": 10, "font_color": navy, "text_wrap": True, "valign": "top"})
    int_fmt = wb.add_format({"font_name": "Aptos", "font_size": 10, "font_color": navy, "num_format": "0", "align": "center"})
    pct_fmt = wb.add_format({"font_name": "Aptos", "font_size": 10, "font_color": navy, "num_format": "+0.0%;-0.0%;0.0%"})
    date_fmt = wb.add_format({"font_name": "Aptos", "font_size": 9, "font_color": gray, "num_format": "yyyy-mm-dd"})
    num_fmt = wb.add_format({"font_name": "Aptos", "font_size": 9, "font_color": navy, "num_format": "0.00"})
    note_fmt = wb.add_format({"font_name": "Aptos", "font_size": 9, "font_color": gray, "text_wrap": True, "bg_color": light})

    ws = wb.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_tab_color(blue)
    ws.merge_range("A1:G1", "미국 AI 밸류체인 3개월 로테이션", title_fmt)
    ws.merge_range("A2:G2", f"2026-06-01~2026-08-31 · 종목별 시작값=100 · 밸류체인별 동일가중 · 가격수익률(배당 제외)", subtitle_fmt)
    headers = list(summary.columns)
    for c, h in enumerate(headers):
        ws.write(3, c, h, header_fmt)
    for r, row in summary.iterrows():
        rr = r + 4
        ws.write(rr, 0, row["밸류체인"], text_fmt)
        ws.write(rr, 1, row["구성 종목"], wrap_fmt)
        ws.write_number(rr, 2, int(row["종목 수"]), int_fmt)
        for c, key in enumerate(headers[3:], start=3):
            if key == "3개월 수익률":
                # Formula retains a cached value for non-Excel renderers.
                col = xlsxwriter.utility.xl_col_to_name(list(basket_idx.columns).index(row["밸류체인"]) + 1)
                ws.write_formula(rr, c, f"='Basket Indices'!{col}{len(basket_idx)+1}/100-1", pct_fmt, float(row[key]))
            else:
                ws.write_number(rr, c, float(row[key]), pct_fmt)
    ws.set_column("A:A", 24)
    ws.set_column("B:B", 52)
    ws.set_column("C:C", 10)
    ws.set_column("D:G", 17)
    ws.set_row(3, 30)
    ws.autofilter(3, 0, 3 + len(summary), len(headers) - 1)
    ws.freeze_panes(4, 0)
    ws.conditional_format(4, 3, 3 + len(summary), 6, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    ws.insert_image("I2", str(OUT_BAR), {"x_scale": 0.52, "y_scale": 0.52})
    ws.insert_image("I24", str(OUT_HEAT), {"x_scale": 0.53, "y_scale": 0.53})
    ws.write("A20", "해석 시 유의", header_fmt)
    ws.merge_range("A21:G23", "동일가중은 각 종목의 시가총액 차이를 제거해 밸류체인 내부의 전반적인 확산을 보는 방식이다. 실제 지수 기여도와는 다르다. Yahoo Finance의 일별 비조정 종가를 사용했으며 배당은 제외했다. BQuant 신규 원자료는 2026-09-01까지 통합했지만, 과거 미국 종목 원시계열이 현재 폴더에 없어 3개월 가격 구간은 Yahoo 자료로 보완했다.", note_fmt)

    ws = wb.add_worksheet("Monthly Rotation")
    ws.hide_gridlines(2)
    ws.merge_range("A1:D1", "월별 밸류체인 수익률", title_fmt)
    ws.write_row(2, 0, ["밸류체인"] + list(monthly.columns), header_fmt)
    for r, (name, vals) in enumerate(monthly.iterrows(), start=3):
        ws.write(r, 0, name, text_fmt)
        for c, v in enumerate(vals, start=1):
            ws.write_number(r, c, float(v), pct_fmt)
    ws.set_column("A:A", 25)
    ws.set_column("B:D", 15)
    ws.conditional_format(3, 1, 2 + len(monthly), 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    ws.insert_image("F2", str(OUT_HEAT), {"x_scale": 0.65, "y_scale": 0.65})

    ws = wb.add_worksheet("Basket Definitions")
    ws.hide_gridlines(2)
    ws.merge_range("A1:D1", "밸류체인 정의와 구성 종목", title_fmt)
    ws.write_row(2, 0, ["밸류체인", "경제적 역할", "구성 종목", "선정 원칙"], header_fmt)
    for r, (name, tickers) in enumerate(BASKETS.items(), start=3):
        ws.write(r, 0, name, text_fmt)
        ws.write(r, 1, DESCRIPTIONS[name], wrap_fmt)
        ws.write(r, 2, ", ".join(tickers), wrap_fmt)
        ws.write(r, 3, "미국 상장·유동성·AI 매출/수주/설비투자 노출을 우선. 중복을 줄이기 위해 주된 이익 동인 기준으로 1개 바스켓에만 배치.", wrap_fmt)
        ws.set_row(r, 48)
    ws.set_column("A:A", 25)
    ws.set_column("B:B", 55)
    ws.set_column("C:C", 42)
    ws.set_column("D:D", 50)

    ws = wb.add_worksheet("Raw Prices")
    ws.hide_gridlines(2)
    ws.write_row(0, 0, ["Date"] + list(prices.columns), header_fmt)
    for r, (dt, vals) in enumerate(prices.iterrows(), start=1):
        ws.write_datetime(r, 0, dt.to_pydatetime(), date_fmt)
        for c, v in enumerate(vals, start=1):
            ws.write_number(r, c, float(v), num_fmt)
    ws.freeze_panes(1, 1)
    ws.set_column(0, 0, 12)
    ws.set_column(1, len(prices.columns), 11)

    ws = wb.add_worksheet("Normalized Stocks")
    ws.hide_gridlines(2)
    ws.write_row(0, 0, ["Date"] + list(normalized.columns), header_fmt)
    for r, (dt, vals) in enumerate(normalized.iterrows(), start=1):
        ws.write_datetime(r, 0, dt.to_pydatetime(), date_fmt)
        for c, v in enumerate(vals, start=1):
            col = xlsxwriter.utility.xl_col_to_name(c)
            ws.write_formula(r, c, f"='Raw Prices'!{col}{r+1}/'Raw Prices'!{col}$2*100", num_fmt, float(v))
    ws.freeze_panes(1, 1)
    ws.set_column(0, 0, 12)
    ws.set_column(1, len(normalized.columns), 11)

    ws = wb.add_worksheet("Basket Indices")
    ws.hide_gridlines(2)
    ws.write_row(0, 0, ["Date"] + list(basket_idx.columns), header_fmt)
    for r, (dt, vals) in enumerate(basket_idx.iterrows(), start=1):
        ws.write_datetime(r, 0, dt.to_pydatetime(), date_fmt)
        for c, v in enumerate(vals, start=1):
            ws.write_number(r, c, float(v), num_fmt)
    ws.freeze_panes(1, 1)
    ws.set_column(0, 0, 12)
    ws.set_column(1, len(basket_idx.columns), 19)
    ws.insert_image("P2", str(OUT_LINE), {"x_scale": 0.55, "y_scale": 0.55})

    ws = wb.add_worksheet("Methodology")
    ws.hide_gridlines(2)
    ws.merge_range("A1:F1", "방법론·데이터 출처", title_fmt)
    methods = [
        ("가격", "Yahoo Finance chart API의 일별 비조정 종가. 2026-06-01~2026-08-31. 배당 제외."),
        ("동일가중", "각 종목을 최초 공통 거래일 가격으로 100에 정규화한 뒤 바스켓 내 산술평균. 기간 중 리밸런싱 없음."),
        ("종목선정", "미국 거래소 상장 보통주·ADR 중 유동성이 높고 해당 밸류체인을 주된 AI 노출로 설명할 수 있는 종목을 선정."),
        ("BQuant 연결", "신규 Bquant_All_19_Raw_Refreshed12시 (1).xlsb는 기존 19개 지수 그룹 원자료에 중복일자를 교체하고 2026-09-01까지 이어 붙임."),
        ("제약", "동일가중 성과는 투자 가능한 공식 지수가 아니며 거래비용·세금·배당·환율을 반영하지 않음. 서사 해석은 수익률과 공식 기업 실적 발표를 함께 사용."),
    ]
    ws.write_row(2, 0, ["항목", "설명"], header_fmt)
    for r, (k, v) in enumerate(methods, start=3):
        ws.write(r, 0, k, text_fmt)
        ws.write(r, 1, v, wrap_fmt)
        ws.set_row(r, 45)
    ws.set_column("A:A", 18)
    ws.set_column("B:B", 105)
    wb.close()

    # Text snapshot used by the report builder.
    payload = {
        "date_start": str(prices.index.min().date()),
        "date_end": str(prices.index.max().date()),
        "summary": summary.to_dict(orient="records"),
        "monthly": {name: {m: float(v) for m, v in row.items()} for name, row in monthly.iterrows()},
        "failures": failures,
    }
    (OUT_DIR / "US_AI_Value_Chain_3M_Rotation_20260901.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", OUT_XLSX)
    print(summary.to_string(index=False, formatters={"3개월 수익률": pct, "최근 1개월 수익률": pct, "3개월 최대낙폭": pct, "SPY 대비 3개월": pct}))
    print(monthly.map(lambda x: pct(float(x))).to_string())


if __name__ == "__main__":
    main()
