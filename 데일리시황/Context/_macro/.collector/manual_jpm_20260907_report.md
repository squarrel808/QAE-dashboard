# JPM manual Chrome download, 2026-09-07

- Requested window: 2026-09-01 through 2026-09-07 inclusive, publication dates shown by JPM.
- Scope: the user's existing Economics Commetary search, Most Recent sort; existing logged-in Chrome.
- Result: 71 unique original PDFs downloaded and copied into `../outdated/JPM/`, total 37,039,307 bytes.
- Each file passed `%PDF-` header, final 4 KiB `%%EOF`, and source/destination SHA-256 equality checks. Original files remain in `C:\Users\infomax\Downloads`.
- Detailed source URLs, dates, original paths, saved paths, sizes, and SHA-256 are in `manual_jpm_20260907_manifest.csv`. Raw UI title/date ledger: `manual_jpm_20260907.tsv`.
- Search pages 1–3 were traversed. Page 3 reached 31 Aug 2026 at `GPS-5431105-0`, immediately after the final 1 Sep item `GPS-5431504-0`.
- Two new 7 Sep reports arrived during collection: `GPS-5438947-0` and `GPS-5438994-0`. Page 1 was refreshed and both were downloaded; overlapping pagination records were deduplicated by report ID.
- No observed download failures or missing PDFs within this search/window. This does not claim coverage of other JPM searches or reports published after the final refresh.
- Downloads used the visible report-row download buttons; no standalone collector, copied credentials, browser profile extraction, or direct HTTP requests were used.
- The standalone collector SQLite database was not changed by this manual-browser workflow. The separate manifest is the authoritative record for this run.
