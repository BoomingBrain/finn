# Task 0 — Data source spikes

Run on **Wed 28 Oct 2026** from the developer's Mac (residential IP). **Status: complete**, including the cloud check from GitHub Actions. Scripts are in `spikes/`; every real response is saved under `backend/tests/fixtures/`. Per the plan's Global Constraints, **this file overrides any endpoint, field name or source choice written in the plan.**

## Findings

| Source | Works locally | Works from GitHub Actions | Auth / limits | Primary choice | Fallback |
|---|---|---|---|---|---|
| NSE announcements API (`/api/corporate-announcements`) | ✅ 200 for INFY, HDFCBANK, RELIANCE (13–19 items each, ~0.7 s) with httpx after a cookie warm-up GET on the homepage. Plain `curl` gets 403. | ✅ 200 for all 3 (14/19/13 items). The homepage warm-up got 403, yet the API still answered. | Cookie warm-up + browser UA + `Referer`. No limit seen at 3 req / 2 s. | **NSE** | Local ingest via `make ingest` if Actions is blocked. BSE is **not** a fallback (see next row). |
| BSE announcements API (`api.bseindia.com`) | ❌ 403 "Access Denied" (Akamai) | — | Bot protection. Getting past it would need TLS-fingerprint impersonation, which we **will not do**. | — | — |
| NSE archive PDFs (`nsearchives.nseindia.com`) | ⚠️ INFY OK (26.7 MB). **HDFCBANK truncated**: server sends `content-length: 983040` while the real file is ~1.14 MB; the PDF won't open (0 pages). Range requests are ignored. | ✅ 200, full 26.7 MB INFY file | none | NSE archive | **BSE file server** via screener.in's quarter "Raw PDF" link (`/company/source/quarter/{id}/{M}/{YYYY}/` → 302 → `bseindia.com/xml-data/corpfiling/AttachHis/…pdf`). Got the full 24-page HDFCBANK file with a plain client. |
| screener.in company page | ✅ 200, **no login wall**, all sections present. 20 rapid requests → 20 × 200 (no 429). | ✅ 200, no login wall, document links present | none seen | **screener.in** | — (cache responses 24 h anyway) |
| screener.in → transcript / AR PDFs | ✅ links point to `bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=…` and download fine (PIDILITIND Aug 2026 transcript, 305 KB). | ✅ BSE file server 200, full HDFCBANK PDF (1,193,121 bytes) | none | screener links | — |
| yfinance EOD (`.NS`) | ✅ INFY.NS, HDFCBANK.NS | ✅ returns bars | none seen | **yfinance** | — |
| LLM extraction of results numbers (NVIDIA API) | ✅ **97% (64/66 fields over 3 runs)** with `nemotron-3.5-super-vl` reading the page image; the one deterministic misread is fixed by a 200-dpi re-read | n/a | ~40 RPM per key (community figure) | **vision model on the page image** | OCR text is unusable (18%) |

## LLM provider: NVIDIA API catalog (tested 28 Oct)

The user chose NVIDIA's free hosted models over Anthropic.
- Endpoint: `https://integrate.api.nvidia.com/v1/chat/completions`, using the OpenAI request format.
- Key: one `nvapi-` key in `.env` as `NVIDIA_API_KEY`. The user's line has a space before `=`, so the loader must strip whitespace.
- Limit: ~40 requests/min, shared across all models.

### Model access

| Model | Access | Latency ("Reply OK") | Role |
|---|---|---|---|
| `nvidia/nemotron-3.5-super-vl-120b-a12b` | ✅ | 13.5 s cold, ~7 s per results page | **Vision: results extraction** |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | ✅ | 1.6 s | **Bulk text:** classification fallback, summaries, profiles, guidance targets, explanations. Send `chat_template_kwargs: {"enable_thinking": false}`; otherwise it spends ~125 hidden reasoning tokens even on "OK". |
| `nvidia/nemotron-3-ultra-550b-a55b` | ✅ | 2.8 s | **Reasoning:** Bull vs Bear |
| `nvidia/nemotron-parse-2.0` | ✅ | 7 s/page | Not used. Its table output is excellent, but the 4,096-token total limit truncates long pages, and the parse → text → JSON chain mis-aligned columns (3%). |
| `moonshotai/kimi-k2.6` | ❌ 404 "Function not found for account" | — | not available on this key |
| `deepseek-ai/deepseek-v4.1-flash` | ❌ timed out (180 s) | — | — |
| `z-ai/glm-5.3`, `z-ai/glm-5.3-flash` | ❌ timed out (90 s) | — | — |

**Pattern:** third-party models on the free tier timed out or were unavailable; NVIDIA's own Nemotron models were fast. Stick to Nemotron. The bulk backup is the same lightning model with thinking enabled, not another vendor.

### Results extraction accuracy

Scored by `spikes/results_llm_spike.py` against the hand-checked values below: 33 fields per run (INFY 18, HDFCBANK 15).

| Pipeline | INFY | HDFCBANK | Total | Time/page |
|---|---|---|---|---|
| **B: page image → super-vl → JSON** | 18/18 ×3 | 14/15 ×3 | **97%** | ~7 s |
| C: PDF OCR text → lightning → JSON | 6/18 | 0/15 | 18% | 5–22 s |
| A: nemotron-parse → lightning → JSON | 1/18 | 0/15 | 3% | 27–41 s |

- **The miss is deterministic:** B misreads HDFCBANK Q2 PBT as 26,909.8 (true 25,909.8) on every run, so retrying identically won't help.
- **Arithmetic catches it:** 26,909.8 − tax 6,399.84 ≠ PAT 19,509.96.
- **A targeted re-read fixes it:** re-sending the page at **200 dpi** with the failed check named returns 25,909.8, and all checks pass (2 s). The same request at the lower resolution did not fix it.

### Task 4 design (this overrides the plan)

1. Select the statement page by keyword score on the OCR text, which is good enough to *find* the page but not to read it.
2. Render the page to fit 1664×2048 and send the image to `nemotron-3.5-super-vl` with thinking off. Extract, per column: `revenue, other_income, total_income, finance_costs, depreciation, interest_earned, interest_expended, ppop, provisions, pbt, tax, pat`.
3. Run arithmetic checks in code:
   - corporates: `revenue + other_income ≈ total_income` and `pbt − tax ≈ pat`
   - lenders: `ppop − provisions ≈ pbt` and `pbt − tax ≈ pat`
   - tolerance 0.5%; skip a check whose inputs are null
4. On a failed check, re-read once at 200 dpi with a hint naming the failed rows and column.
5. If it still fails, mark the card `unreadable`. Then apply the screener cross-check (Task 14) as the last line of defence.

## Facts later tasks must use

### Announcements (Task 3)
- Fields: `symbol, sm_name, desc, attchmntText, attchmntFile, an_dt, sort_date, dt, seq_id, sm_isin, smIndustry, fileSize, attFileSize, hasXbrl, exchdisstime, orgid, bflag, csvName, difference, old_new`.
- `sort_date` = `"YYYY-MM-DD HH:MM:SS"` in IST. `attchmntFile` = absolute `https://nsearchives.nseindia.com/corporate/…pdf`.
- **`desc` is NSE's coarse category** ("Updates", "General Updates", "Outcome of Board Meeting", "Analysts/Institutional Investor Meet/Con. Call Updates", "Change in Management", "Copy of Newspaper Publication", "ESOP/ESOS/ESPS", "Shareholders meeting", "Credit Rating", "Record Date"…). **The real subject is in `attchmntText`.** Map `subject = attchmntText`, `raw_category = desc`, and classify on both.
- Transcripts arrive as `desc = "Analysts/Institutional Investor Meet/Con. Call Updates"` with the text "…about Transcript". The `earnings_call` rule must look at the text, or these become `investor_meetings`.
- Results arrive as `desc = "Outcome of Board Meeting"` with text "…submitted to the Exchange, Financial Results for the quarter…".

### Results PDFs (Task 4)
- **Size and page selection:** filings can be huge. INFY's board outcome is **195 pages / 26.7 MB**: cover letter, IFRS fact sheet (p3–6), consolidated Ind AS statement (**p18**), standalone (p22), auditor reports, IFRS financials, press release. **Do not take "the first 6 pages".** Select pages by keyword score: title matching `Statement of (Consolidated|Standalone) .*Results`, plus `Revenue from operations`/`Interest earned`, plus `Profit before tax`. Prefer Ind AS consolidated, and skip pages titled "Fact Sheet" / "IFRS".
- **The text layer is often lossy OCR of a scan:**
  - INFY p18: the OCR lost the first rows entirely. The current quarter's Revenue (49,244) and Other income (848) are missing from the text.
  - HDFCBANK p2: column-header dates are scrambled ("31.03.2026 / 30.09.2026 / 30.06.2026 / 39.09.2026"), some decimals use commas ("79362,78"), and the letter O replaces zero ("4OO O18").
  - **Consequence:** use OCR text only to *find* the statement page. Send the selected page as a **150-dpi PNG image** to Haiku for extraction (to be confirmed by `results_llm_spike.py`).
- **Column order:** both filings follow the SEBI standard: quarter (current, previous, year-ago), then half-year (current, prior), then full year. `select_quarter_columns` must **fall back to this order** when the extracted `period_end` dates are missing or inconsistent. Add a test with a scrambled date.
- **Units:** both filings are in ₹ crore ("In ₹ crore", "(₹ in crore)"). No lakhs example yet. Find one for the Task 14 gold set (small caps often report in lakhs).
- **Bad downloads:** every downloaded PDF must be validated (`page_count > 0`). On failure, fetch the same filing through screener's "Raw PDF" link for that quarter.

### Hand-checked values (gold for Tasks 4 and 14)

Read from the rendered page images. Every column passes its internal arithmetic checks (Revenue + OI = Total income; PPOP − provisions = PBT; PBT − tax = PAT).

**INFY** — consolidated, Ind AS, ₹ crore, fixture `results/INFY_q2fy27_statements.pdf` page 5 (original p18)

| | Q2 FY27 (30 Sep 2026) | Q1 FY27 (30 Jun 2026) | Q2 FY26 (30 Sep 2025) |
|---|---|---|---|
| Revenue from operations | 49,244 | 48,211 | 44,490 |
| Other income | 848 | 984 | 982 |
| Finance cost | 115 | 119 | 106 |
| Depreciation & amortisation | 1,359 | 1,246 | 1,182 |
| PBT | 11,063 | 11,028 | 10,229 |
| PAT (profit for the period) | 7,838 | 7,775 | 7,375 |
| **EBITDA** (PBT + fin + dep − OI) | **11,689** | **11,409** | **10,535** |

**HDFCBANK** — standalone, ₹ crore, fixture `results/HDFCBANK_q2fy27.pdf` page 2 (consolidated is on page 9)

| | Q2 FY27 | Q1 FY27 | Q2 FY26 |
|---|---|---|---|
| Interest earned | 83,426.60 | 79,362.78 | 76,690.70 |
| Interest expended | 48,807.42 | 45,828.83 | 45,139.20 |
| **NII** | **34,619.18** | **33,533.95** | **31,551.50** |
| PPOP | 29,483.42 | 28,168.06 | 27,923.60 |
| PBT | 25,909.80 | 25,108.30 | 24,423.07 |
| PAT | 19,509.96 | 19,059.72 | 18,641.28 |

### screener.in (Tasks 9, 10, 14)
- **Parser:** selectolax ≥ 1.0 removed the old parser, so use `from selectolax.lexbor import LexborHTMLParser`.
- **Sections:** `section#quarters`, `#profit-loss`, `#balance-sheet`, `#cash-flow`, `#ratios`, `#shareholding`, `#documents`. Row labels carry a trailing `+` (strip it).
- **Quarter columns** look like `"Sep 2026"`. 13 quarters are shown.
- **Corporate quarter rows:** `Sales, Expenses, Operating Profit, OPM %, Other Income, Interest, Depreciation, Profit before tax, Tax %, Net Profit, EPS in Rs, Raw PDF`.
- **Bank quarter rows:** `Revenue, Interest, Expenses, Financing Profit, Financing Margin %, Other Income, Depreciation, Profit before tax, Tax %, Net Profit, EPS in Rs, Gross NPA %, Net NPA %, Raw PDF`.
  - **`Financing Profit` is negative** for HDFCBANK (−5,565 in Sep 2026). It is not PPOP or operating profit.
  - Remove `"Financing Profit"` and `"Financing Margin %"` from `ROW_ALIASES` (Task 9). Bank OPM is `None`.
- **Cross-check validated:** screener's INFY quarters equal the filing exactly. Sales 49,244 / 48,211 / 44,490; PBT 11,063 / 11,028 / 10,229; Net Profit 7,838 / 7,775 / 7,375.
  - Screener's **"Operating Profit" = our EBITDA formula** (11,689 / 11,409 / 10,535), so `crosscheck` can compare EBITDA too for corporates.
- **Basis:** screener's HDFCBANK page is consolidated (Sep 2026 Net Profit 21,537 vs standalone 19,509.96). The cross-check must compare the same basis.
- **Freshness:** INFY's Sep 2026 quarter was already on screener 5 days after filing. PIDILITIND has not reported Q2 FY27 yet (latest column Jun 2026).
- **Documents:** `#documents` has "Annual reports" (15 for each test company; links to BSE `AttachHis`) and "Concalls" (`<li>`: a month-level date such as "Aug 2026", plus links labelled "Transcript", "PPT", "REC", "Notes"). PIDILITIND has 58 transcripts and HDFCBANK 21. **Transcript dates are month-level only**, so set `said_on` to the 1st of that month.
- Each quarter column has a "Raw PDF" link (`/company/source/quarter/{company_id}/{month}/{year}/`) that redirects to the results PDF on BSE. This is the PDF fallback.

### Prices (Task 7)
- yfinance returns **a partial bar for the current session during market hours**. On 28 Oct, INFY showed −4.8% on ~6.2 M shares vs ~20–26 M on full days. `detect_signals` must ignore today's bar unless it is past 16:00 IST. Ingest runs scheduled before the close must drop it.

## Choices

- **Thursday slice stock: INFY.** Results were filed 23 Oct 2026 16:08 IST, with a newspaper ad (24 Oct) and the auditor's report (23 Oct) filed alongside. That is a natural clustering example. Screener has the matching quarter for the cross-check.
- **Lender example: HDFCBANK.** Results filed 17 Oct, plus the earnings-call presentation, recording link and transcript, and two management-change filings (30 Sep, 1 Oct). Good for profile cards too.
- **No BSE API fallback for announcements.** If NSE blocks the Actions runner, announcements are ingested locally (`make ingest`), and Actions only does what works from the cloud.

## Cloud check (GitHub Actions run 40646213614, 28 Oct, Azure IP)

Every source works from a cloud runner. NSE announcements, screener.in, the NSE archive, the BSE file server and yfinance all returned 200 with full payloads. So scheduled ingestion (Task 8) can run on Actions, and the Render live-research service should reach screener.in and BSE. Render's own IPs are still untested and will be verified in Task 12.

## Fixtures saved

| File | What |
|---|---|
| `announcements_nse_{INFY,HDFCBANK,RELIANCE}.json` | 30 days of raw NSE announcements |
| `screener_{PIDILITIND,HDFCBANK,INFY}.html` | Consolidated company pages (corporate, bank, slice stock) |
| `results/INFY_q2fy27_statements.pdf` | INFY Q2 FY27 results, trimmed to 6 pages: fact sheet p1–4, consolidated statement p5, standalone p6 (original was 195 pp / 26.7 MB) |
| `results/HDFCBANK_q2fy27.pdf` | HDFCBANK Q2 FY27 results, full 24 pages (from the BSE file server) |
| `transcripts/PIDILITIND_Aug_2026.pdf` | PIDILITIND Q1 FY27 concall transcript |
