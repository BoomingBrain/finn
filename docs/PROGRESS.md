# FINN — Progress Log

Plan: [superpowers/plans/2026-10-28-finn.md](superpowers/plans/2026-10-28-finn.md) · Deadline: **Sun 1 Nov 2026**

## Status

| # | Task | Day | Status | Commit | Notes |
|---|---|---|---|---|---|
| 0 | Data spikes | Wed | ✅ Done | 247448d | NSE ✅, screener ✅, yfinance ✅, BSE API ❌. Deferred: LLM extraction check (to Task 4), Actions cloud check (no remote) |
| 1 | Foundation: models, snapshot store, LLM router, spend budget | Wed | ⬜ Not started | | |
| 2 | Skeleton deploy: one service, web shell | Wed | ⬜ Not started | | |
| 3 | Announcements source and classification | Thu | ⬜ Not started | | |
| 4 | Results card: column selection, units, lender layout | Thu | ⬜ Not started | | |
| 5 | Vertical slice: ingest → Brief for one stock, deployed | Thu | ⬜ Not started | | |
| 6 | Widen to 18 stocks, event clustering, profiles | Fri | ⬜ Not started | | |
| 7 | Prices, signals, alerts, Watch with backtest sliders | Fri | ⬜ Not started | | |
| 8 | Scheduled ingestion | Fri | ⬜ Not started | | |
| 9 | screener.in source and deterministic metrics | Sat | ⬜ Not started | | |
| 10 | Promised vs Delivered | Sat | ⬜ Not started | | |
| 11 | Dossier builder, citation guard, precompute demo set | Sat | ⬜ Not started | | |
| 12 | Research API, live fetch fallback, cost guard | Sat | ⬜ Not started | | |
| 13 | Ask screen and "Ask about this" | Sat | ⬜ Not started | | |
| 14 | Accuracy eval and results cross-check | Sun | ⬜ Not started | | |
| 15 | Polish, README, writeup, build history, submit | Sun | ⬜ Not started | | |

Legend: ⬜ Not started · 🟨 In progress · ✅ Done · ⛔ Blocked · ✂️ Cut

## Nightly checkpoints

| Night | "Demo must work" | Result |
|---|---|---|
| Wed 28 | Deployed shell opens on a phone; spikes recorded | Spikes done (2 checks deferred) |
| Thu 29 | Deployed Brief shows one real results card | |
| Fri 30 | Brief + Watch on all 18 stocks; lender cards; backtest sliders | |
| Sat 31 | 4 demo dossiers instant; unseen ticker streams or fails cleanly | |
| Sun 1 | Accuracy in README; submission sent | |

## Accuracy (filled by Task 14)

_Not run yet._

## Log

Newest first.

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
