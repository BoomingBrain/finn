# FINN — Progress Log

Plan: [superpowers/plans/2026-10-28-finn.md](superpowers/plans/2026-10-28-finn.md) · Deadline: **Sun 1 Nov 2026**

## Status

| # | Task | Day | Status | Commit | Notes |
|---|---|---|---|---|---|
| 0 | Data spikes | Wed | ✅ Done | see log | NSE ✅, screener ✅, yfinance ✅, NVIDIA vision extraction 97% ✅, BSE API ❌. Cloud check from GitHub Actions ✅ |
| 1 | Foundation: models, snapshot store, LLM router, request budget | Wed | ✅ Done | see log | 3/3 budget tests; smoke: snapshot round trip, real cached NVIDIA call |
| 2 | Skeleton deploy: static site on HF Space, API on Render | Wed | ✅ Done | Space e6a2ac6 | Live: https://ayush-rai-230265-finn.static.hf.space · Render https://finn-zztc.onrender.com (health + CORS OK) |
| 3 | Announcements source and classification | Thu | ✅ Done | see log | 48 rule tests; live 30d: 224 filings, rules 92%, 1 LLM call |
| 4 | Results card: column selection, units, lender layout | Thu | ✅ Done | see log | 25 tests; real INFY + HDFCBANK cards 100% match hand-checks |
| 5 | Vertical slice: ingest → Brief for one stock, deployed | Thu | ✅ Done | 367a14a | Live: INFY results card on the Brief (30d window) |
| 6 | Widen to 18 stocks, event clustering, profiles | Fri | ✅ Done | 2ba5d7b | 18 stocks: 230 filings → 184 events; 8 results cards; 11 profiles; deployed |
| 7 | Prices, signals, alerts, Watch with backtest sliders | Fri | ✅ Done | 8e7293f | Live: alerts inbox + badge, unusual moves in Brief, sliders with 30-day evidence. Step 5 (notifications) ✂️ cut |
| 8 | Scheduled ingestion | Fri | ✅ Done | 317dad2 | Actions every 2 h on market days + 19:00 IST daily; 2 runs green; Render ignores data commits |
| 9 | screener.in source and deterministic metrics | Sat | ✅ Done | see log | 11 metric tests; live KOTAKBANK/NAUKRI/CDSL + unknown ticker OK |
| 10 | Promised vs Delivered | Sat | ✅ Done | see log | 27 guidance tests; Pidilite 4 calls: FY26 margin met (24.1% vs 20–24%), FY27 pending at 26.2% |
| 11 | Dossier builder, citation guard, precompute demo set | Sat | 🟨 In progress | cb2b03e | Code done; 22-ticker precompute running (reason tier is slow) |
| 12 | Research API, live fetch fallback, cost guard | Sat | ✅ Done | cb2b03e | Live on Render: 404 unknown, replay, Render reaches screener.in. 9 guard/API tests |
| 13 | Ask screen and "Ask about this" | Sat | 🟨 In progress | | Built + 20 web tests; deploy after the precompute finishes |
| 14 | Accuracy eval and results cross-check | Wed | ✅ Done | see log | Results 57/57 fields; guidance recall 3/3, precision 100%; 8/8 live cards verified vs screener |
| 15 | Polish, README, writeup, build history, submit | Sun | ⬜ Not started | | |

Legend: ⬜ Not started · 🟨 In progress · ✅ Done · ⛔ Blocked · ✂️ Cut

## Nightly checkpoints

| Night | "Demo must work" | Result |
|---|---|---|
| Wed 28 | Deployed shell opens on a phone; spikes recorded | ✅ Spikes done incl. cloud check; shell live on the Space, Ask shows Render ready (headless check). Phone check: user |
| Thu 29 | Deployed Brief shows one real results card | ✅ Met early (28 Oct): live Brief serves INFY Q2 FY27 card from events.json. Phone check: user |
| Fri 30 | Brief + Watch on all 18 stocks; lender cards; backtest sliders | ✅ Met early (28 Oct): all live, data refreshes on schedule |
| Sat 31 | 4 demo dossiers instant; unseen ticker streams or fails cleanly | |
| Sun 1 | Accuracy in README; submission sent | |

## Accuracy (filled by Task 14)

`make eval`, 28 Oct 2026. Gold values were read by hand from the rendered pages (`backend/eval/*.yaml`).

### Results extraction (field accuracy, within 0.5%)

| Filing | Correct | Misses |
|---|---|---|
| INFY Q2 FY27 (consolidated, Ind AS) | 12/12 | — |
| HDFCBANK Q2 FY27 (bank, consolidated) | 12/12 | — |
| BAJFINANCE Q2 FY27 (NBFC, consolidated; no PPOP line printed) | 9/9 | — |
| PIDILITIND Q4 FY26 (quarter and full-year columns, Rs crores) | 12/12 | — |
| POLYCAB Q2 FY27 (reported in ₹ million) | 12/12 | — |
| **Total** | **57/57 (100%)** | |

### Guidance extraction (Promised vs Delivered)

| Call | Gold targets | Found | Extracted | False positives |
|---|---|---|---|---|
| PIDILITIND Aug 2026 call | 1 | 1 | 2 | 0: — |
| HAL May 2026 call | 2 | 2 | 5 | 0: — |
| CDSL Aug 2026 call | 0 | 0 | 0 | 0: — |
| **Total** | 3 | recall **3/3** | | precision **100%** |

## Log

Newest first.

### 2026-10-28 — Dossiers saved permanently and kept current (user request)
- **`finn/persist.py`:** a `GitHubStore` commits a finished live dossier to `data/snapshot/dossiers/{SYM}.json` via GitHub's contents API. The server replays saved dossiers before building, so after a restart a dossier is not rebuilt. It is a no-op without the `GITHUB_TOKEN` env var on Render, and a dossier with a failed section is never saved. 4 tests with a mocked API, plus 2 API tests (saved and replayed after a restart; failed one not saved).
- **Staleness:** `source_fingerprint(company)` = latest results quarter, latest concall date, latest annual-report year, stored on every dossier. `needs_build()` returns "missing", "a section failed" or "new sources". CLI `--mode all|missing|failed|refresh`; `--all` now includes every saved dossier.
- **`.github/workflows/dossiers.yml`:** daily 20:00 IST, `--mode refresh`, commit (rebase first) and deploy. The ingest workflow also rebases before pushing now.
- **Web:** the dossier header says what it covers and when it was built.
- **Needs from the user:** a fine-grained GitHub token (Contents: read and write, this repo only) as `GITHUB_TOKEN` on Render.

### 2026-10-28 — Task 14 complete: accuracy eval and screener cross-check
- **`push/crosscheck.py`:** each readable results card is compared with screener's matching quarter (Revenue and PAT; PAT only for lenders) at 2% tolerance. Result: `verified` True/False with `mismatches`, or None (other basis, quarter not on screener, unreadable card). Runs in ingest; a screener failure leaves cards unmarked. 7 tests.
- **Dry run on the live cards:** 8/8 verified (KPITTECH, LT, INFY, BAJFINANCE, HDFCBANK, PERSISTENT, POLYCAB, DMART).
- **Gold set (`backend/eval/`):**
  - **Results, 5 filings:** INFY, HDFCBANK (bank), BAJFINANCE (NBFC, no PPOP line), PIDILITIND Q4 with full-year columns, POLYCAB in ₹ million (no portfolio company reports in lakhs; millions exercises the same unit conversion).
  - **Transcripts, 3 calls:** PIDILITIND Aug 2026, HAL May 2026, CDSL Aug 2026 (no targets: a precision check). Candidates were found by grepping for numbers near forward-looking words and judged by hand; statements without a fiscal period are "acceptable" (neither required nor false positives).
- **`make eval`:** results 57/57 fields within 0.5%; guidance recall 3/3, precision 100%. Small gold set, so read these as "no known errors", not a population rate.

### 2026-10-28 — Tasks 11–13: dossiers, research API, Ask screen
- **Task 11 (`pull/sections.py`, `pull/dossier.py`):** `GROUNDING_RULES` opens every prompt; `drop_uncited` runs on every model output; segment shares not printed on the cited page are blanked. Sections stream in fixed order with fixed reasons.
  - **First precompute exposed two bugs, both fixed with tests:**
    - The 550B reasoning model timed out and returned 429s with about 16 parallel calls. `llm.py` now caps calls in flight per tier (reason = 2), gives thinking calls a 300 s timeout, and retries with 5/20/60 s backoff.
    - Every annual report names the "Independent Auditor's Report" in its contents (pages 2–4), which cut the narrative to zero pages; mentions in the first 10% are now ignored. The BRSR "Description of Business Activity" table is always included: it gives each business's share (ITC: Cigarettes 45.88%, p352).
  - PDF cache writes are now atomic (temp + rename).
  - ITC has no concall transcripts (it holds no earnings calls), so its delivery section correctly reads "No concall transcripts on screener.in".
- **Task 12 (`guard.py`, `api.py`):** `RateLimiter` (sliding hour), `nse_symbols.csv` (2,618 NSE symbols), `symbols.json` written by ingest and the dossier CLI. `GET /api/research/{symbol}` (SSE): precomputed replay → 404 unknown → in-memory live cache → per-IP limit → daily budget → live build with keep-alive comments every 15 s; `SourceUnreachable` → fixed error event. Render: commit live in ~80 s; NOTATICKER → 404; a live PIDILITIND build streamed its snapshot within 30 s, so **Render reaches screener.in**.
- **Task 13 (web):** `useResearch` (static file first, else fetch-streamed SSE so 404/429 are visible; "Waking the research server" after 5 s), SymbolSearch (≤ 8 matches, demo chips), ContextStrip from `#/ask/SYM?event=id`, Snapshot tiles + sparklines + flags, Delivery scorecard ("N of M checkable promises met", quotes with page chips), Business, Bull vs bear, "Ask about this" on every event card. Checked at 390 px.

### 2026-10-28 — Task 10 complete: Promised vs Delivered
- **`finn/pull/guidance.py`:** `GuidanceTarget`, `resolve_period` (Indian FY: FY27 = Jun 2026 … Mar 2027; Q/H/FY, 2- or 4-digit years), `actual_for` (growth = period ÷ same quarters a year earlier; margin = Σ op profit ÷ Σ revenue; sums for revenue/PAT; partial periods give the tracking value), `judge`, `extract_targets`, `explain`, `assess_delivery`.
- **Code judges, model explains.** The verdict is computed before the model sees the row and is passed as fixed; a line that names a different verdict ("missed" for a met row) is replaced by the template. Not-checkable rows never reach the model.
- **Grounding guards on extraction:**
  - the page id must be one that was sent (brackets stripped)
  - ≥ 80% of the quote's words must be on that page
  - `forward_looking` must be true, which drops past results
  - zero values are dropped
  - unlisted metrics (e.g. `volume_growth`) become `other`; one malformed item is dropped alone instead of failing the reply
- **Changes from the plan, with evidence:**
  - **Extraction uses the reason tier, not bulk.** On the Pidilite Aug 2026 call the bulk model labelled past results, volume growth and "1x–2x GDP" as revenue targets; the reasoning model returned only the real target (20–24% EBITDA margin band). Chunks of 16k chars run in parallel (4 workers); about 45–115 s per transcript.
  - **`between` counts beating the top of the range as met.** Every checkable metric is higher-is-better; Pidilite running at 26.2% against a 20–24% band is not a miss.
- **Live smoke (Pidilite, last 4 transcripts):** 10 targets → 5 rows after dedupe. FY26 margin **met** (24.1% over 4 quarters, matches Task 9's annual OPM); FY27 margin **pending** (26.2% after Q1, hand-checked 1,194 ÷ 4,552); capex, A&SP and price-over-volume spread **not checkable**. Quotes verified on the cited pages (p12, p19 of the Aug 2026 call).
- 167 backend tests pass.

### 2026-10-28 — Task 9 complete: screener.in source + metrics
- **`finn/sources/screener.py`:**
  - lexbor parser: tables with "+" stripped from row names, "Raw PDF" links per quarter, annual reports (dated 31 Mar of the year), and concall transcripts (month dates, newest first)
  - `fetch_company`: consolidated, else the standalone fallback; 24 h disk cache
  - `CompanyNotFound` (404) / `SourceUnreachable`
- **`finn/pull/metrics.py`:** TTM (last 4 quarters), 3-year revenue/PAT CAGR, operating margin now vs 3 years ago (computed from rows, because screener's OPM % is integer-rounded), ROCE/ROE, D/E, 3-year CFO÷PAT, the last 8 quarters, and red flags (cash conversion < 0.7, D/E > 1, margins down > 3 points). Lenders get no OPM, D/E or CFO/PAT. Missing inputs give None, never 0; a CAGR from a non-positive base is None.
- **TDD:** 11 tests on the real PIDILITIND and HDFCBANK fixtures (values worked from the printed table numbers, arithmetic in comments) plus synthetic flag, missing-value and negative-base cases.
- **Live smoke:** KOTAKBANK (unseen bank) is auto-detected as a lender (rev CAGR 18.3%, ROE 11%). CDSL flags "Margins compressing" (57.5% → 50.8%). NAUKRI's PAT CAGR is None (negative base). NOTATICKER123 raises CompanyNotFound.

### 2026-10-28 — Task 8 complete: scheduled ingestion
- **`.github/workflows/ingest.yml`:**
  - cron `0 4-12/2 * * 1-5` plus `30 13 * * *`, and `workflow_dispatch` with a `days` input
  - a rolling `actions/cache` of `backend/.cache` (LLM responses + PDFs)
  - ingest → commit `data/snapshot` as finn-ingest[bot] → `make deploy-space`
  - `concurrency: ingest`; `permissions: contents: write`
- **`make ingest`** is the local fallback: pull, ingest, commit, push, deploy.
- **Secrets:** my `gh secret set` (option A) was blocked by the permission system (secret-store write), so the user added the 4 repo secrets by hand.
- **Run 40661158462:** all steps green. 59 fetched, 0 new (no LLM calls), snapshot committed, Space redeployed; live `as_of` 14:32 IST.
- **Render check:** `/api/health` now reports `RENDER_GIT_COMMIT`. A code push deployed in ~45 s (2a68757). After the data-only ingest commit 5e8905e (run 40661573309), Render stayed on 2a68757 for 4+ min, confirming the root-directory filter, so the 2-hourly runs cost no Render build minutes.
- **Workflow change:** the bot now commits to `main`, so local work must `git pull --rebase` before pushing.

### 2026-10-28 — Task 7 complete: signals, alerts, Watch
- **Backend:** `finn/push/signals.daily_metrics` gives per-session change % and volume ÷ the 20 previous sessions. It skips NaN bars and today's bar before 16:00 IST (6 tests). Ingest writes `signals.json` (18 symbols × 60 sessions, with names).
- **Browser** (`web/src/lib/signals.ts`, 4 tests): `signalsFor` / `backtest` / `alertsFor` apply the investor's thresholds to the precomputed metrics. Settings (clamped) and seen alerts live in localStorage and are lifted to `App`, so the badge, the inbox and the Brief stay in step.
- **Watch:**
  - "N new alerts." with an inbox (unread dots, two-line titles, "Mark all as seen"); tapping a filing alert opens its card in the Brief (`#/brief/<id>`, widening the window if needed).
  - Sliders with live evidence ("Would have fired 6 times in the last 30 days. Mostly KPIT (2) …").
  - Category toggles.
- **Brief:** "Unusual moves, by your thresholds" between critical and notable.
- **Review of the live data led to a judgment change.** 7 days showed 15 critical items, including Titan setting up a CAD 5,000 Canadian subsidiary and routine NCD allotments. Housekeeping is now notable (subsidiary incorporation, strike-off or winding up, unless it's an acquisition or divestment; NCD/CP/bond allotments, while equity raises stay critical), and filing alerts need critical. Result: 12 critical in 7 days (results ×4, management ×2, regulatory ×3, a QIP, the Jio IPO, Trent's divestment). 10 tier tests.
- **Evidence the sliders surface:** the default 2× volume threshold would have fired 30 times in 30 days, price ±5% 6 times.
- **Cut:** Step 5 (in-app notifications): the data only changes on redeploy, so it would never fire mid-visit.
- **Next step noted:** grade regulatory fines by size relative to the company (IRCTC ₹10 lakh and DMart ₹55.75 lakh are still critical).
- **Tests:** backend 129, web 11. Deployed (10 files, 844 KB); live `signals.json` and the Watch sliders verified.

### 2026-10-28 — Task 6 complete: whole portfolio, clustering, profiles
- **`finn/push/cluster.py`:**
  - same symbol + category within 36 h → one event
  - headline member: results > profile > tier > earliest
  - all documents linked
  - price move and volume multiple on the first tradable session of the headline filing (after-close filings → next session; an unsettled session → none)
  - 14 tests
- **`finn/sources/prices.py` (`fetch_eod`)** was pulled forward from Task 7. It drops today's bar before 16:00 IST.
- **`extract_profile`:** the appointee (or leaver) from the filing; scanned filings are read as images; "Not Applicable" becomes an empty bio, shown as "No profile in filing".
- **Real run, 18 stocks × 30 days:** 230 filings → 184 events (55 critical / 33 notable / 96 routine), ~6.6 min, 94 bulk + 15 vision calls. **8 results cards:** BAJFINANCE (NII), DMART, HDFCBANK (NII/PPOP), INFY, KPITTECH, LT, PERSISTENT (₹ millions → Cr; EBITDA missing), POLYCAB. **11 management-change profiles**, e.g. HDFC Bank's new MD & CEO Anup Bagchi.
- **Smoke-found fixes, each with a failing test first:**
  1. ZIP attachments (3 KMP filings).
  2. Persistent's results sat under "Outcome of the Board Meeting": the PDF now decides whether there's a statement, and a rule replaces a flaky LLM label.
  3. "Not Applicable" bios.
  4. Regulation 30 boilerplate in headlines.
  5. NBFC total-income check (interest income ≠ total revenue).
  6. Tax: accept the printed total or the summed components (Bajaj's components were incomplete).
  7. A missing EBITDA input no longer hides verified Revenue/PBT/PAT.
  8. `ingest --reprocess` keeps categories (it had re-asked the LLM, which flipped a label).
- **Tests:** backend 113, web 7. Deployed (9 files, 712 KB); live events.json verified.

### 2026-10-28 — Task 5 complete: vertical slice live
- **Backend:**
  - `finn/push/enrich.py`: results statement → `ResultsCard` (vision); other critical/notable → a one-line summary (bulk, ≤ 140 chars, clipped at a word); routine → no download, no LLM call; failures degrade only that item.
  - `finn/push/events.py`: `to_event` plus `headline()`, which strips "X has informed the Exchange regarding".
  - `finn/ingest.py`: incremental fetch → classify → enrich, 60-day retention, writes `push.json` and `events.json`; CLI `python -m finn.ingest`.
  - Snapshot files are now written 0644.
- **Real run (INFY, 30 days):** 14 filings, 7 enriched, ~31 s. The card reads Revenue 49,244 (+10.7% YoY), EBITDA 11,689, PBT 11,063, PAT 7,838; summaries are concrete (₹26 interim dividend, record date 3 Nov).
- **Web:**
  - Brief with window chips (24h/3d/7d/30d, remembered per device), tiered event rows, results table (Indian grouping, true minus, up/down colour), collapsed routine group, quiet/stale/empty/error states.
  - A dev-only Vite plugin serves `data/snapshot` at `/data`; a path-traversal probe returns only the SPA fallback.
- **Tests:** web 7 (ResultsCard 4 per plan, plus 3 small digest tests); backend still 76.
- **Visual check** at a true 390 px via a same-origin frame wrapper (a file:// wrapper failed because third-party storage is blocked in the frame).
- **Deployed:** `make deploy-space` (8 files, 208 KB); live `events.json` verified; live page renders the Brief.
- **Known:** INFY's newspaper ad and auditor's report show as separate critical rows until Task 6 clustering.

### 2026-10-28 — Task 4 complete: results card
- **`finn/sources/documents.py`:** PDF download validated with `page_count > 0`, with fallback URLs (for NSE truncation), a disk cache, page text, and page PNGs (fit 1664×2048 or a set dpi).
- **`finn/push/results.py`:**
  - `select_statement_page` needs income + PBT rows, prefers a results title and consolidated, and skips fact sheets/IFRS/auditor pages.
  - `select_quarter_columns` matches end dates 80–100 / 355–375 days apart, with a SEBI column-order fallback when dates are garbled.
  - `check_arithmetic`: total income; PPOP − provisions = PBT; PBT − tax + after-tax items = PAT.
  - `compute_results`: corporate or lender layout; it refuses (`unreadable`) on any failed check, missing value, or |PAT| > Revenue.
  - `extract_results`: a vision read, plus one 200-dpi re-read naming the failed checks.
- **TDD:** 25 tests, including the deterministic Task 0 HDFCBANK PBT misread, after-tax items (associates), lenient "(173)"/"49,244"/garbled-date parsing, the re-read flow with a fake LLM, and page selection on the real fixtures.
- **Smoke found a real bug:** the model *added* INFY's current + deferred tax wrongly (2,225 vs 3,225), and the check correctly refused the card. Fix: the model copies `tax_current`/`tax_deferred`, and code sums them. After the fix, **INFY (consolidated) and HDFCBANK (consolidated) match the hand-checks exactly**; HDFCBANK PBT/PAT also match screener.in. HDFCBANK consolidated gold values were added to `docs/spikes.md`.

### 2026-10-28 — Task 3 complete: announcements + classification
- **`finn/sources/announcements.py`:** an NSE client (cookie warm-up, re-warm on 401/403, 0.5 s spacing) using the Task 0 field mapping. One failing symbol never drops the rest.
- **`finn/push/classify.py`:**
  - ordered regex rules over NSE category + subject + attachment filename
  - `TIER_BY_CATEGORY` per Decisions
  - `tier_for()` makes scheduling notices routine (e.g. "Infosys to Announce Second Quarter Results")
  - one bulk LLM call per 25 leftovers, with out-of-enum answers → unclassified
- **TDD:** 48 tests, written from real filings. The first live run exposed 8 misses (order wins, "Action(s) initiated", "Non Convertible Securities", QIP inside a run-together filename, guarantees, "Analyst(s)/Investor(s) meet", Q2/H1 analyst presentations). Each was added as a failing test, then fixed.
- **Live smoke, all 18 holdings over 30 days:** 224 announcements in 19 s, 0 failures. Rules classify 205 (92%); the 19 leftovers took **one** LLM call. Tiers: 75 critical / 35 notable / 114 routine (results season; Task 6 clustering will fold results-day bundles).
- **Known limitation:** some leftovers say almost nothing ("Outcome of Committee Meeting"), so the LLM guesses (e.g. postal_ballot for a Persistent committee outcome). They land in routine or notable. A later improvement is to read the attachment's first page for leftovers only.

### 2026-10-28 — Task 2 complete: live deploy
- **Render:** the user created `finn-research` at https://finn-zztc.onrender.com (Singapore, free). `/api/health` returns 200 in 0.3–0.7 s; the CORS preflight from the Space origin is allowed.
- **Space:** `make deploy-space` pushed 6 files (172 KB) to `Ayush-Rai-230265/finn` (Space commit e6a2ac6). https://ayush-rai-230265-finn.static.hf.space serves `<title>FINN</title>`, and the bundle contains the Render URL. `.env` and backend paths are not served.
- **End to end:** a headless load of the live Ask tab shows the green "Live research server is ready", proving the Space → Render cross-origin call works.
- **Remaining for the Wed checkpoint:** the user opens the URL on a phone.

### 2026-10-28 — Task 2 (in progress)
- **Plan updated** for the HF Static Space + Render split (Architecture, Decisions, Global Constraints, File Structure, Tasks 2, 5, 7, 8, 11, 12, 13). The digest, alerts and backtest now run in the browser over precomputed `events.json` / `signals.json`; Render does only live research; all 22 dossiers are precomputed.
- **Web shell** (`web/`, Vite + React 18 + Tailwind v4, PWA manifest): three tabs (Brief / Watch / Ask), hash routes, and a Render health indicator on Ask. Design follows the frontend-design skill:
  - blue-black ink background, marigold only for critical, colour only for tier and direction
  - Newsreader for one statement per screen, Public Sans with tabular figures
  - checked by headless-Chrome screenshots inside exact 360/390 px frames (raw headless screenshots enforce a ~500 px minimum width and looked clipped)
- **`backend/finn/api.py`:** `/api/health` plus CORS limited to `WEB_ORIGIN` and localhost:5173. The smoke check confirmed allowed and denied origins.
- **`scripts/deploy_space.sh` / `make deploy-space`:** builds, assembles only the site + `data/`, refuses `.env`/PDF/`.py`/`backend`, and force-pushes with a one-shot credential helper. The dry run produced 6 files (172 KB), and the guard was verified to fire.

### 2026-10-28 — Deploy setup and the cloud check
- **Hosting:** Hugging Face Docker and Gradio Spaces are now paid for free accounts, so the user created a **Static** Space, `Ayush-Rai-230265/finn`. Live research moves to a **free Render web service**.
- **GitHub:** a private repo, `BoomingBrain/finn`, is connected and pushed. A repo-local credential helper uses the `BoomingBrain` gh login; the global active account (`debugat2am`) is unchanged. `.env` and the challenge PDFs are not in the repo (verified).
- **Permission rules** the user added: `Bash(make deploy-space)`, `Bash(git push origin main)`.
- **Task 0's cloud check ran on GitHub Actions** (run 40646213614): every source returned 200 from a cloud IP.
- **Next:** update the plan for the static Space + Render split, then build Task 2.

### 2026-10-28 — Task 1 foundation
- `backend/` is a uv project (Python 3.12). Added `finn/models.py` (all shared shapes; `filed_at` is normalised to IST), `finn/snapshot.py` (atomic JSON writes under `data/snapshot/`), `finn/portfolio.yaml` and `finn/portfolio.py` (18 holdings + 4 research tickers; HDFCBANK = Banks, BAJFINANCE = NBFC), and `finn/llm.py`.
- `finn/llm.py` has:
  - tier → NVIDIA model routing, overridable with `FINN_MODEL_<TIER>`
  - thinking off for the bulk and vision tiers
  - a 35/min throttle and a daily `RequestBudget`
  - a SQLite response cache keyed on model, prompt, schema and image hashes
  - per-model usage totals
  - one JSON-repair retry
  - one retry on 429/5xx
- **Tests:** `tests/test_budget.py` 3/3 pass (it failed first on the missing module, as TDD expects).
- **Smoke:** a PushSnapshot round trip with the IST timezone preserved and no temp files left; the portfolio loads 18 + 4; Settings rejects out-of-range values. A real bulk call classified "Appointment of … CFO" as `management_change` in 1.0 s (59 in / 8 out tokens); the repeat came from the cache in 0 ms with usage unchanged.

### 2026-10-28 — Task 0 complete: LLM provider switched to NVIDIA
- **Provider:** the user chose NVIDIA's free API catalog over Anthropic. One `nvapi-` key in `.env`.
- **Model access:** NVIDIA's own Nemotron models work and are fast. Kimi K2.6 returned 404 (not on this account); DeepSeek V4.1 Flash and GLM 5.3 timed out.
- **Models chosen:**
  - vision `nemotron-3.5-super-vl-120b-a12b`
  - bulk `nemotron-3.5-lightning-30b-a3b` (thinking off)
  - reason `nemotron-3-ultra-550b-a55b`
- **Results extraction, scored against the hand-checked values:**
  - **page image → vision model: 97% (64/66 fields over 3 runs).**
  - PDF OCR text → text model: 18%.
  - nemotron-parse → text model: 3%.
- **The single miss (HDFCBANK Q2 PBT, one digit) repeats on every run.** Arithmetic checks (PBT − tax ≠ PAT) catch it, and a 200-dpi re-read fixes it. Task 4 now uses read → check arithmetic → re-read once → else "unreadable".
- **Plan updated:** Tech Stack, the Models decision, the cost constraint (a request budget plus a 35/min throttle, since the models are free), Task 1 `llm.py` interfaces and tests, the Task 2 secrets, Task 4 extraction, and Task 12 env vars.
- **Removed** the unused `anthropic` package from the spike environment.

### 2026-10-28 — Task 0 closed
- The user closed Task 0 and asked to keep everything **local**, with no GitHub repo for now.
- **Deferred:** the LLM extraction check moves to the start of Task 4 (needs `ANTHROPIC_API_KEY`). The Actions cloud check waits until a repo exists. Ingestion is assumed local.
- **Heads-up:** Task 2 (deploy sync from GitHub to HF Spaces) and Task 8 (Actions ingest cron) assume a GitHub remote. Revisit them before starting.

### 2026-10-28 — Task 0 data spikes
- **NSE announcements work** locally with httpx plus a cookie warm-up (plain curl gets 403). Fixtures were saved for INFY, HDFCBANK and RELIANCE. `desc` is only a coarse category; the real subject is in `attchmntText`.
- **The BSE API is blocked** (Akamai 403). Bypassing it would need browser-fingerprint impersonation, which we won't use. So BSE is not an announcements fallback; the fallback is local ingest.
- **The NSE archive truncated the HDFCBANK results PDF** (`content-length` 983,040 < real size). The fix is to validate every PDF and fall back to screener's "Raw PDF" link, which goes to the BSE file server and returned the full file.
- **screener.in works:** no login, no 429 after 20 rapid requests, transcripts and annual reports download. **Its INFY quarter numbers match the filing exactly, and its "Operating Profit" equals our EBITDA formula**, which validates the cross-check design. Bank "Financing Profit" is negative and must not be used as operating profit.
- **Results PDFs can be huge** (INFY: 195 pp / 26.7 MB). The statement pages are scans with lossy OCR: INFY lost its Revenue row, and HDFCBANK has scrambled header dates and comma decimals. The plan changes to keyword page selection, sending the page image to Haiku, and a SEBI column-order fallback. All details are in `docs/spikes.md`.
- **Hand-checked gold values** for INFY (consolidated) and HDFCBANK (standalone) are recorded in `docs/spikes.md`.
- **yfinance works**, but it returns a partial intraday bar; signals must ignore today's bar before 16:00 IST.
- **Slice stock for Thursday: INFY.**
- **Pending:** run `spikes/results_llm_spike.py` (needs `ANTHROPIC_API_KEY`) and the GitHub Actions cloud check (needs a GitHub repo).
- Initialised the local git repo and committed the spikes and fixtures.

### 2026-10-28
- Revised the plan from review feedback (prompt #5). Changes:
  - added Task 0 data spikes
  - reordered into a vertical slice, with the skeleton deployed on day 1
  - cut tests to the silent-failure logic only
  - offline ingestion with committed snapshots and one HF Spaces service
  - spend cap and per-IP rate limit
  - lender results layout
  - code-computed Promised-vs-Delivered verdicts
  - accuracy eval and screener cross-check
  - event clustering
  - "Ask about this" and backtest sliders
  - day-by-day schedule and cut list
- Read the challenge brief and the reference PDF and wrote the first 16-task plan. Added task descriptions, plus this log and the [prompt log](PROMPTS.md).
- **Open:** user to review the revised plan and choose an execution mode.
