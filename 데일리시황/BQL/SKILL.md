---
name: bql
description: Build, audit, and optimize Bloomberg BQL formulas and Bloomberg-enabled Excel workbooks for index, sector, and constituent analysis. Use for BQL(), BQL.Query(), members(), filtered universes, historical estimate series, EPS revision breadth, index-weighted contribution analysis, Bloomberg ticker-limit reduction, or validation against the BQLX Excel whitepaper.
---

# Bloomberg BQL Excel

Build compact Bloomberg Excel workbooks that batch data server-side, preserve Bloomberg output layouts, and calculate transparent index contributions in ordinary Excel formulas.

When resuming the Europe index/sector/stock project, read `memory.md` in this folder before editing files.

## Core workflow

1. Identify whether the requested result is for an index itself, sector subindices, or index constituents.
2. Prefer one multi-item BQL request over separate BDP, BDH, or per-field BQL requests.
3. Use the index ticker directly for official index-level series.
4. Use `members(['Index'])` only when constituent weights, breadth, filtering, or bottom-up aggregation is required.
5. Reserve a hidden spill/output range and map it into a formatted visible table with `INDEX`, `MATCH`, `SUMIFS`, or `COUNTIFS`.
6. Keep Bloomberg calls separate from derived Excel calculations and contribution formulas.
7. Validate syntax, array ranges, column mappings, units, definitions, and Bloomberg-call count before delivery.
8. Require a final refresh in Bloomberg-enabled Excel; do not claim entitlement-level execution was verified offline.

## BQLX-verified Excel syntax

The primary source is `C:\Users\infomax\Downloads\BQLX.pdf`, especially pages 100-111.

### BQL formula structure

Use:

```excel
=BQL("Universe", "Expression", "Optional Parameter", "Optional Local Variable")
```

- Separate multiple tickers in a `BQL()` universe with commas:

```excel
=BQL("IBM US Equity, MSFT US Equity", "px_last")
```

- Do not put square-bracket ticker lists directly in the first argument of ordinary `BQL()` unless they are inside a universe function.
- Use square brackets inside `members()`:

```excel
=BQL("members(['SX5E Index'])", "name().value, id().weights")
```

- `members('SX5E Index')` also appears in Bloomberg examples, but standardize generated workbooks on `members(['SX5E Index'])`.

### Current and historical dates

- Omit the date for current data and current membership.
- Use `0D` for today inside BQL syntax.
- Never place Excel `TODAY()` inside a quoted BQL string.
- Convert an Excel/Bloomberg date for query construction with:

```excel
=BQL.Date(BToday())
```

- Request monthly history with separate global parameters:

```excel
=BQL(
  "SX5E Index",
  "px_last, pe_ratio(fpt=BT,fpo=1,ae=E)",
  "dates=range(2016-08-01,0D)",
  "per=M",
  "fill=PREV"
)
```

- Do not use `frq=cm` as the global periodicity for an ordinary historical `BQL()` request. `frq` may be valid inside functions such as `iterationdates=range(...)`; keep that usage separate from the global `per=M` parameter.

### Display parameters

Use explicit display parameters whenever Excel formulas depend on the returned column order:

```excel
"showids=True", "showdates=False", "showheaders=True"
```

- `showids`: return or hide universe IDs.
- `showdates`: return or hide observation dates.
- `showheaders`: return or hide output headers.
- `transpose=True`: return a horizontal rather than vertical table.
- `xlsort=ASC|DESC`: control time-series date order.
- `groupbyfields=True|False`: group output by field or identifier first.

### Local variables

Pass each local variable as its own quoted argument and prefix its name with `#`:

```excel
=BQL(
  "members(['SXXP Index'])",
  "(sum(group(#up))-sum(group(#down)))/(sum(group(#up))+sum(group(#down))) as #ERI",
  "#up=contributor_revisions(is_eps(fpt=A,fpo=1,ae=E),NUMUP,4W)",
  "#down=contributor_revisions(is_eps(fpt=A,fpo=1,ae=E),NUMDN,4W)"
)
```

### BQL.List and BQL.Query

- `BQL.List()` converts securities to BQL list syntax for use by `BQL.Query()`.
- A `BQL.List()` result cannot be referenced inside ordinary `BQL()`, which already converts comma-separated tickers into a list.
- Use `BQL.Query()` only when raw `let() get() for() with()` syntax materially simplifies a complex query.

## Batch query design

### Multi-security snapshot

Batch multiple securities and multiple fields into a single request:

```excel
=BQL(
  "SXXP Index, SX5E Index, DAX Index",
  "px_last().value as #Price, pe_ratio(fpt=BT,fpo=1,ae=E).value as #PE_NTM, is_eps(fpt=BT,fpo=1,ae=E).value as #EPS_NTM",
  "showids=True",
  "showdates=False"
)
```

### Filtered constituent snapshot

Do not retrieve the member list and then issue one request per stock. Filter and retrieve all fields in the same server-side request:

```excel
=BQL(
  "filter(members(['"&$B$2&"']),cur_mkt_cap>="&$D$2&")",
  "name().value as #Name, classification_name(gics,1) as #Sector, country_full_name().value as #Country, id().weights as #Weight, cur_mkt_cap().value as #MarketCap, px_last().value as #Price, is_eps(fpt=BT,fpo=1,ae=E).value as #EPS_NTM, pe_ratio(fpt=BT,fpo=1,ae=E).value as #PE_NTM",
  "showids=True",
  "showdates=False",
  "showheaders=True"
)
```

Treat the market-cap unit as a field/output convention to verify through BQLX or FLDS. Make the threshold visible and user-editable. Use zero to include every member.

## Metric definitions

Keep these concepts separate:

- `FY1 EPS Growth = FY1 EPS / FY0 EPS - 1`.
- `FY2 EPS Growth = FY2 EPS / FY1 EPS - 1`.
- `Rev. 1M/3M/6M`: percentage change in the relevant consensus EPS series over the stated window.
- Analyst Up/Down: contributor revision-event counts over the stated window.
- Stock ERI: `(Analyst Up - Analyst Down) / (Analyst Up + Analyst Down)`.
- Index breadth: share or count of members with upward/downward revisions; state whether members can appear in both measures.
- Expected margin delta: forward expected operating/EBIT margin less latest actual margin, in percentage points.
- P/E percentile: current forward P/E ranked against the specified historical monthly window.

Do not call consensus EPS percentage change and contributor-revision event counts the same measure.

## Contribution calculations

Normalize Bloomberg index weights to Excel fractions before multiplying:

```excel
=IF(RawWeight>1,RawWeight/100,RawWeight)
```

Calculate:

- EPS revision contribution: `Index Weight * Rev. 1M`.
- FY1 EPS growth contribution: `Index Weight * FY1 EPS Growth`.
- Weighted breadth contribution: `Index Weight * SIGN(Rev. 1M)`.
- Earnings-yield contribution: `Index Weight * (1 / Forward P/E)`.
- Implied aggregate P/E: `1 / SUM(Earnings-yield contributions)`.

Never aggregate P/E with `SUM(weight * P/E)`. P/E is a ratio; aggregate its reciprocal, earnings yield.

State that weight-times-growth is a practical attribution approximation and may not equal Bloomberg's official index EPS aggregation because of methodology, negative earners, currency, divisor, float weights, and rebalancing.

## Excel implementation

CRITICAL RULE (learned from the 2026-08-18 refresh failure): **never write BQL formulas as legacy CSE array formulas (`openpyxl` `ArrayFormula` / `<f t="array" ref="...">`).** BQL is a dynamic-array function; a CSE array over the reserved range gets exploded by Excel/the Bloomberg add-in into one independent copy of the formula per cell, which floods the terminal with duplicate queries, fills the range with `#VALUE!`, shifts row-relative references out of range, and triggers Bloomberg's "delete faulty functions" prompt.

SECOND CRITICAL RULE (learned the same day): **plain `<f>` storage of `_xll.*` formulas also fails** — Excel's repair removes them on open (`recoveryLog: 제거된 레코드 ... 수식`). The only openpyxl storage form verified to load cleanly is a **single-cell array formula** whose ref is the anchor itself:

```python
from openpyxl.worksheet.formula import ArrayFormula
ws["B7"] = ArrayFormula(ref="B7", text='=_xll.BQL("members([\'SX5E Index\'])","name().value")')
```

THIRD RULE — prefer the user's proven "B22 pattern" over server-side BQL aggregation: one BQL that returns only the filtered member ticker list (`filter(members(['SPX Index'], dates=TODAY()), cur_mkt_cap >= 50000000000)`, `"name().value"`), a header row of API field mnemonics, and per-cell `=BDP($ticker, field$header)` formulas; history via `=BDH(ticker, "PX_LAST", "-10CY", "", "Per=cm")`. The header-driven grid means the user swaps any FLDS mnemonic without touching formulas. Field mnemonics verified working in his environment: SECURITY_NAME, GICS_SECTOR_NAME, CHG_PCT_1D, CHG_PCT_5D, PX_LAST. Note `dates=TODAY()` inside the BQL string works on his terminal, and `cur_mkt_cap` filters in raw currency units.

- Reserve enough empty rows and columns below/right of the anchor for the dynamic spill; any content in that region causes `#SPILL!`.
- Make every cell reference inside a concatenated BQL string fully absolute (`$A$7`, never `$A7`), so no copy/conversion can shift it.
- Put `dates=range(...)`, `per=M`, `fill=PREV` **inside each data item's parentheses** (BQLX pp.101/105 documents this as equivalent to global parameters). Evidence from the failed refresh suggests separate global date parameters may be silently ignored with aliased/derived expressions (inference, not verified fact).
- Never overlap reserved spill ranges.
- Hide raw Bloomberg ranges only after confirming their mappings.
- Use ordinary Excel formulas for visible tables and derived fields.
- Apply Arial and the workbook's existing financial-model color conventions.
- Set workbook calculation to automatic/full calculation on load.
- Ship a small `BQL_Test` sheet of isolated one-cell tests (verified syntax first, unverified constructs last) so refresh failures can be attributed to a specific construct.

Known Bloomberg error signatures and their meaning:

- `#N/A Invalid Security: ... Input failed to evaluate: ""` — the universe string concatenated to an empty cell (broken reference).
- `#N/A Invalid Parameter: Function MEMBERS encountered an unexpected error` — members()/filter() request failed server-side; check construct validity and query flooding.
- Whole range `#VALUE!` with one stray spilled table — CSE array explosion (see rule above).

Do not run LibreOffice recalculation on Bloomberg `_xll.BQL` workbooks. LibreOffice does not have the Bloomberg add-in and can replace formulas with `#NAME?`. Validate formula text and array structure offline, then refresh in Bloomberg-enabled Excel.

## Validation checklist

Before delivery:

1. Confirm every Bloomberg formula contains `_xll.BQL` and no obsolete BDP/BDH formulas remain when a BQL-only workbook was requested.
2. Confirm no BQL formula is stored as a CSE array (`t="array"`): every one must be a plain single-cell formula.
3. Confirm no formula contains literal `#REF!`, `#DIV/0!`, or `#NAME?`, and no reserved spill range overlaps another or contains content.
4. Confirm ordinary history uses `dates=range(...)`, `per=M`, and `fill=PREV` inside the data item's parentheses.
5. Confirm no quoted BQL formula contains Excel `TODAY()`.
6. Confirm constituent universes use `members(['Index'])`.
7. Confirm `showids`, `showdates`, and `showheaders` match the raw-column mapping.
8. Confirm raw-output columns feed the intended visible fields.
9. Confirm weight units and percentage storage conventions.
10. Count Bloomberg calls and report the reduction achieved by batching.
11. Add a visible note that data-item availability and entitlements require a Bloomberg Excel refresh.

## Limitations

The general BQLX Excel whitepaper verifies query structure, date syntax, universes, and display parameters. It is not a complete catalogue for every equity estimate or index item. For an unsupported item, verify the data item and its parameters through BQLX, FLDS, or the Bloomberg Function Builder rather than substituting an API mnemonic such as `BEST_EPS` inside BQL.
