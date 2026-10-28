# CPI Monitor

`/cpidist` opens CPI Distribution and 기여도 views. Distribution starts with Core CPI heatmaps for all 26 selected Haver country/regional series, followed by the existing distribution embed.

## Refresh

Run `python macro_hub/scripts/build_cpi_analysis.py --fetch` from the repository root after DLX Direct login. The existing CPI Excel collector also runs this refresh on successful completion. Without `--fetch`, the script rebuilds the public JSON from the saved raw snapshot. The Vercel application reads only `public/data/cpi_analysis.json` and needs no Haver credentials.

`--manifest` is a maintenance operation: it reconstructs the candidate mapping from local Haver catalogs and explicit overrides. Review mappings before fetching. The committed manifest contains 63 nonoverlapping components across six countries. Canada splits alcohol, tobacco and cannabis to keep price/weight definitions consistent. Latest basket weights sum to 100% within source rounding.

## Definitions

- Contributions are explicitly labeled estimates, not official published contributions. For lag k=1 (MoM) or k=12 (YoY), calculate `(index[t]/index[t-k]-1)*100 * weight[t-k]/100`. The table exposes both current and reference-period weights. Changes to baskets and chain-linking can cause the stacked sum to differ from headline CPI.
- Component indices use NSA observations. Missing price observations are never forward-filled. Weights may carry forward their last published observation. Negative contributions stack below zero.
- Core YoY uses the selected seasonally adjusted index. 3M/3M annualized is `((mean(last 3 months)/mean(previous 3 months))**4-1)*100`. All six calendar months must exist. Country-specific exclusions remain visible in tooltips; Australia's trimmed mean is explicitly named. New Zealand's quarterly series has only YoY values on quarter-end months.
- Haver queries are grouped by native frequency and responses mapped by full ticker, preventing automatic aggregation of monthly prices to quarterly/annual frequency.
- Full history begins in 2017 where available; UI dates reflect actual observed dates. No synthetic inflation or missing-month interpolation is used.

Validation: `python macro_hub/scripts/test_cpi_analysis.py`, `npx tsc --noEmit`, `npm run build`, and browser interaction checks.
