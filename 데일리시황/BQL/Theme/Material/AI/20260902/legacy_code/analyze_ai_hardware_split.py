from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SOURCE = Path(r"C:\Users\USER\Downloads\유로존\Bquant_All_19_Grouped_Raw_Updated_20260901.xlsx")
OUT_DIR = Path(r"C:\Users\USER\Downloads\Telegram Desktop\ChatExport_2026-08-09 (2)\research_tmp")

NEEDLES = [
    "Micron", "SK hynix", "Samsung Electronics", "Taiwan Semiconductor",
    "ASML", "Applied Materials", "Lam Research", "KLA Corp", "Teradyne",
    "Comfort Systems", "Quanta Services", "EMCOR", "GE Vernova", "Vertiv",
    "Siemens Energy", "Schneider Electric", "Siemens AG", "ABB Ltd",
]


idx = pd.read_excel(SOURCE, sheet_name="Index_Daily", usecols=["Date", "Index_Code", "Price"])
stk = pd.read_excel(
    SOURCE,
    sheet_name="Stock_Daily",
    usecols=["Date", "Index_Code", "Ticker", "Security_Name", "GICS_Sector", "GICS_Industry_Group", "Price"],
)

matches = stk[stk["Security_Name"].fillna("").str.contains("|".join(NEEDLES), case=False, regex=True)].copy()
latest_pairs = matches[["Index_Code", "Ticker", "Security_Name"]].drop_duplicates().sort_values(["Security_Name", "Index_Code"])
rows = []
for rec in latest_pairs.itertuples(index=False):
    ix = idx[idx.Index_Code.eq(rec.Index_Code)].sort_values("Date").copy()
    if ix.empty:
        continue
    ix["changed"] = ~np.isclose(ix.Price, ix.Price.shift(), rtol=1e-7, atol=1e-9, equal_nan=False)
    sessions = ix.loc[ix.changed, "Date"].tolist()
    if len(sessions) < 11:
        continue
    start, latest = sessions[-11], sessions[-1]
    s = matches[(matches.Index_Code.eq(rec.Index_Code)) & (matches.Ticker.eq(rec.Ticker))]
    a = s[s.Date.eq(start)].drop_duplicates("Ticker")
    b = s[s.Date.eq(latest)].drop_duplicates("Ticker")
    if a.empty or b.empty:
        continue
    rows.append({
        "Name": rec.Security_Name,
        "Ticker": rec.Ticker,
        "Index": rec.Index_Code,
        "Start": start.date(),
        "End": latest.date(),
        "Return_10D": float(b.iloc[0].Price / a.iloc[0].Price - 1),
        "Sector": b.iloc[0].GICS_Sector,
        "Industry": b.iloc[0].GICS_Industry_Group,
    })

out = pd.DataFrame(rows).drop_duplicates(["Ticker", "Index"])
print(out.to_string(index=False, formatters={"Return_10D": lambda x: f"{x:+.2%}"}))

preferred = {
    "MU UW Equity": ("Memory", "Micron"),
    "ASML NA Equity": ("Semi Equipment", "ASML"),
    "AMAT UW Equity": ("Semi Equipment", "Applied Materials"),
    "KLAC UW Equity": ("Semi Equipment", "KLA"),
    "LRCX UW Equity": ("Semi Equipment", "Lam Research"),
    "TER UW Equity": ("Semi Equipment", "Teradyne"),
    "FIX UN Equity": ("E&C", "Comfort Systems"),
    "EME UN Equity": ("E&C", "EMCOR"),
    "PWR UN Equity": ("E&C", "Quanta Services"),
    "GEV UN Equity": ("Power / Cooling", "GE Vernova"),
    "VRT UN Equity": ("Power / Cooling", "Vertiv"),
    "ENR GY Equity": ("Power / Cooling", "Siemens Energy"),
    "SU FP Equity": ("EU Diversified", "Schneider Electric"),
    "SIE GY Equity": ("EU Diversified", "Siemens"),
    "ABBN SE Equity": ("EU Diversified", "ABB"),
}
chart = out[out.Ticker.isin(preferred)].copy()
chart = chart.sort_values(["Ticker", "Index"]).drop_duplicates("Ticker")
chart["Category"] = chart.Ticker.map(lambda x: preferred[x][0])
chart["Label"] = chart.Ticker.map(lambda x: preferred[x][1])
chart.to_csv(OUT_DIR / "ai_hardware_split_10d.csv", index=False, encoding="utf-8-sig")

colors = {
    "Memory": "#2F6BDE",
    "Semi Equipment": "#7B61A8",
    "E&C": "#D84A4A",
    "Power / Cooling": "#EAAA00",
    "EU Diversified": "#0FA3A3",
}
chart = chart.sort_values("Return_10D")
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(11, 7.5))
bars = ax.barh(chart.Label, chart.Return_10D * 100, color=[colors[c] for c in chart.Category])
ax.axvline(0, color="#102A43", linewidth=1)
ax.grid(axis="x", color="#DCE3EC", linewidth=0.8)
ax.set_title("AI 하드웨어 내부 최근 10거래일 차별화", loc="left", fontsize=19, fontweight="bold", color="#102A43")
ax.set_xlabel("현지통화 가격수익률 (%)")
ax.spines[["top", "right", "left"]].set_visible(False)
for bar, val in zip(bars, chart.Return_10D * 100):
    if val < 0:
        ax.text(val + 0.35, bar.get_y() + bar.get_height()/2, f"{val:.1f}%", va="center", ha="left", color="white", fontsize=9, fontweight="bold")
    else:
        ax.text(val + 0.2, bar.get_y() + bar.get_height()/2, f"+{val:.1f}%", va="center", ha="left", color="#102A43", fontsize=9, fontweight="bold")
handles = [plt.Rectangle((0, 0), 1, 1, color=colors[k]) for k in colors]
ax.legend(handles, list(colors), loc="lower right", frameon=False, fontsize=9)
fig.text(0.01, 0.01, "미국 2026-08-17~08-31, 유럽 2026-08-18~09-01 · BQuant · 배당 미포함", color="#62748A", fontsize=9)
fig.tight_layout(rect=[0, 0.04, 1, 0.96])
fig.savefig(OUT_DIR / "ai_hardware_split_10d.png", dpi=180, facecolor="white")
plt.close(fig)
print(OUT_DIR / "ai_hardware_split_10d.png")
