from pathlib import Path

import pandas as pd


SOURCES = [
    Path(r"C:\Users\USER\Downloads\유로존\Bquant_All_19_Grouped_Raw_Updated_20260901.xlsx"),
    Path(r"C:\Users\USER\Downloads\유로존\dashbaord\Bquant_All_19_Grouped_Raw.xlsx"),
    Path(r"C:\Users\USER\Downloads\유로존\BACKUP\Bquant_All_19_Grouped_Raw.xlsx"),
]
START = pd.Timestamp("2026-06-01")
END = pd.Timestamp("2026-08-31")

BASKETS = {
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

for source in SOURCES:
    if not source.exists():
        print(f"SOURCE MISSING {source}")
        continue
    probe = pd.read_excel(source, sheet_name="Stock_Daily", usecols=["Date"])
    probe["Date"] = pd.to_datetime(probe["Date"])
    print(f"SOURCE {source}: {probe.Date.min().date()} .. {probe.Date.max().date()} rows={len(probe):,}")

stock = pd.read_excel(SOURCES[0], sheet_name="Stock_Daily", usecols=["Date", "Index_Code", "Ticker", "Security_Name", "Price"])
stock["Date"] = pd.to_datetime(stock["Date"])
stock["Root"] = stock["Ticker"].astype(str).str.split().str[0]
window = stock[(stock.Date >= START) & (stock.Date <= END)].copy()

rows = []
for basket, tickers in BASKETS.items():
    for ticker in tickers:
        hit = window[window.Root.eq(ticker)]
        rows.append({
            "Basket": basket,
            "Ticker": ticker,
            "Available": not hit.empty,
            "Date_Count": int(hit.Date.nunique()),
            "Index_Codes": ",".join(sorted(hit.Index_Code.unique())) if not hit.empty else "",
            "BQuant_Tickers": ",".join(sorted(hit.Ticker.unique())) if not hit.empty else "",
            "Security": hit.Security_Name.iloc[0] if not hit.empty else "",
        })

audit = pd.DataFrame(rows)
print(f"BQuant date range: {stock.Date.min().date()} .. {stock.Date.max().date()}")
print(f"Requested window: {START.date()} .. {END.date()}")
print(f"Universe tickers: {len(audit)}")
print(f"Available in BQuant: {audit.Available.sum()}")
print(f"Missing in BQuant: {(~audit.Available).sum()}")
print("\nMISSING")
print(audit.loc[~audit.Available, ["Basket", "Ticker"]].to_string(index=False))
print("\nAVAILABLE COUNTS")
print(audit.loc[audit.Available, ["Basket", "Ticker", "Date_Count", "Index_Codes", "BQuant_Tickers"]].to_string(index=False))
