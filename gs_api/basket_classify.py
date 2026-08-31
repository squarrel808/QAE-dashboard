# -*- coding: utf-8 -*-
"""
basket_classify.py — GS basket 이름/코드 기반 자동 분류기 (순수 파이썬, gs_quant 불필요)
------------------------------------------------------------------------------------
classify(name, bbid, region_meta="", type_meta="") -> dict
  반환 컬럼: category, sector, factor_or_theme, region, needs_review

분류 체계 (category):
  - "HF Positioning"  : VIP vs Short (헤지펀드 crowding)
  - "Factor"          : 전체시장 스타일 팩터 페어 (Growth/Value/Momentum ...)
  - "Sector Factor"   : 특정 섹터 안의 스타일 팩터
  - "Theme"           : 테마성 바스켓 (AI/Software/Reopening ...)
  - "Other / Review"  : 자동 규칙으로 확신 못 함 → 사람이 검토 (needs_review=True)

주: 규칙은 "이름(name)"을 1순위로, bbid 프리픽스를 2순위 힌트로 사용한다.
    미지의 신규 바스켓은 Other/Review 로 떨어지므로, 반환 CSV를 받아 최종 정제한다.
"""
import re

# ── 스타일 팩터 사전 (Barra 계열) : (정규식, 표준라벨) — 위에서부터 먼저 매칭 ──
FACTOR_RULES = [
    (r"growth\s*v(?:s)?\.?\s*value|gro\s*v(?:s)?\.?\s*val", "Growth vs Value"),
    (r"cyclical.*defens|defens.*cyclical",                  "Cyclicals vs Defensives"),
    (r"\bgrowth\b|\bgro\b",                                 "Growth"),
    (r"\bvalue\b|\bval\b",                                  "Value"),
    (r"moment|\bmomo\b",                                    "Momentum"),
    (r"res(?:idual)?\s*vol|low\s*vol|\bvolatility\b|\brsvl\b", "Volatility"),
    (r"\bquality\b|\bqual\b",                               "Quality"),
    (r"\bsize\b",                                           "Size"),
    (r"\bbeta\b",                                           "Beta"),
    (r"\bleverage\b|\blevg\b",                              "Leverage"),
    (r"profitab|\bprof\b",                                  "Profitability"),
    (r"crowd|\bcrwd\b",                                     "Crowding"),
    (r"short\s*interest",                                   "Short Interest"),
    (r"\bdividend\b|\byield\b",                             "Dividend / Yield"),
    (r"\bliquidity\b",                                      "Liquidity"),
]

# ── 테마 사전 : (정규식, 표준라벨) ──
THEME_RULES = [
    (r"\bai\b|artificial intellig|\bgen ?ai\b|\bchat\b", "AI"),
    (r"nonprof|non-?prof",                                "Profitability Theme (Profitable vs Nonprofitable)"),
    (r"mega\s*cap|\bmega\b",                              "Mega Cap"),
    (r"software",                                         "Software"),
    (r"semis?|semiconductor",                             "Semiconductors"),
    (r"\btmt\b",                                          "TMT"),
    (r"reopen|recovery|reflation",                        "Reopening / Reflation"),
    (r"rising rate|rate sensitiv|higher rate|duration",  "Rates Sensitivity"),
    (r"inflation|pricing power",                          "Inflation / Pricing Power"),
    (r"retail favorit|retail sentiment|\bmeme\b",         "Retail / Meme"),
    (r"buyback|capital return|repurchase",               "Buybacks / Capital Return"),
    (r"labou?r|wage",                                     "Labor / Wage"),
    (r"china|onshor|reshor|supply chain|tariff",          "China / Supply Chain"),
    (r"clean energy|renewable|solar|decarbon|\besg\b|climate", "Clean Energy / ESG"),
    (r"obesity|glp-?1|weight loss|drug|pharma",           "Healthcare Innovation"),
    (r"dividend grower|dividend aristocrat",              "Dividend Growers"),
    (r"balance sheet|weak balance|strong balance",       "Balance Sheet Strength"),
    (r"high (?:short|beta)|hedge fund vip|\bvip\b",       "HF / Positioning Theme"),
]

# ── 섹터 사전 (일반 이름용) : (정규식, 표준섹터) ──
SECTOR_RULES = [
    (r"health\s*care|healthcare|\bhc\b",     "Health Care"),
    (r"real\s*estate|\breit\b|\bre\b",       "Real Estate"),
    (r"financ|\bfins?\b",                    "Financials"),
    (r"consumer|\bcons\b",                   "Consumer"),
    (r"industrial|\bindus?\b|\bind\b",       "Industrials"),
    (r"material|\bmats?\b",                  "Materials"),
    (r"\benergy\b|\ben\b",                   "Energy"),
    (r"utilit|\butes?\b",                    "Utilities"),
    (r"telecom|communication|\btels?\b",     "Telecom / Comm Svcs"),
    (r"\btmt\b|semis?|semiconductor|software|\btech\b|\bit\b", "TMT / Tech"),
]

# ── bbid 프리픽스(3~4번째 글자) → 섹터 힌트 (이름이 애매할 때 백업) ──
BBID_SECTOR = {
    "PU": "Broad (US)", "TM": "TMT / Tech", "CN": "Consumer",
    "FI": "Financials", "HC": "Health Care", "IN": "Industrials",
    "EN": "Energy", "MA": "Materials", "UT": "Utilities",
    "RE": "Real Estate", "TL": "Telecom / Comm Svcs",
    "PR": "HF Positioning", "PF": "HF Positioning",
}

REAL_SECTORS = {"Health Care", "Real Estate", "Financials", "Consumer",
                "Industrials", "Materials", "Energy", "Utilities",
                "Telecom / Comm Svcs", "TMT / Tech"}


def _search(rules, text):
    for pat, label in rules:
        if re.search(pat, text, re.I):
            return label
    return None


def _region(name, bbid, region_meta):
    r = (region_meta or "").strip()
    if r:
        return r
    n = (name or "")
    if re.search(r"\beurope\b|\beuro\b|eurozone|stoxx|sx5e|sxxp|\bdax\b|\bcac\b|\bftse\b|\bibex\b|swiss|\bsmi\b|\buk\b", n, re.I):
        return "Europe"
    if re.search(r"\bjapan\b|\bchina\b|\basia\b|\bhk\b|\bkospi\b|topix|nikkei", n, re.I):
        return "Asia"
    if re.search(r"\bus\b|u\.s\.|american?\b", n, re.I) or (bbid or "")[:4] == "GSPU":
        return "Americas (US)"
    return ""


def classify(name, bbid, region_meta="", type_meta=""):
    n = (name or "").strip()
    b = (bbid or "").strip().upper()
    nl = n.lower()

    # 섹터: 이름 우선, 없으면 bbid 프리픽스
    sector = _search(SECTOR_RULES, nl)
    if not sector and len(b) >= 4:
        sector = BBID_SECTOR.get(b[2:4], None)
    if not sector:
        sector = "Broad / Cross-sector"

    factor = _search(FACTOR_RULES, nl)
    theme = _search(THEME_RULES, nl)
    region = _region(n, b, region_meta)

    is_vip = bool(re.search(r"vip\s*v(?:s)?\.?\s*short", nl)) or (b[:4] in ("GSPR", "GSPF"))

    needs_review = False
    if is_vip:
        category = "HF Positioning"
        label = "VIP vs Short"
    elif factor and sector in REAL_SECTORS:
        category = "Sector Factor"
        label = factor
    elif factor:
        category = "Factor"
        label = factor
    elif theme:
        category = "Theme"
        label = theme
    else:
        category = "Other / Review"
        label = ""
        needs_review = True

    # 이름이 비어 신뢰 낮음
    if not n:
        needs_review = True

    return {
        "category": category,
        "sector": sector,
        "factor_or_theme": label,
        "region": region,
        "needs_review": needs_review,
    }


if __name__ == "__main__":
    # 간단 자기검사
    tests = [
        ("GS Growth vs Value", "GSPUGRVA"),
        ("GS AI Pair", "GSPUARTI"),
        ("GS US Consumer Growth", "GSCNGRWT"),
        ("GS US Cons VIP vs Short", "GSPRVSCS"),
        ("GS US TMT Momentum", "GSTMMOMO"),
    ]
    for nm, bb in tests:
        print(bb, nm, "->", classify(nm, bb))
