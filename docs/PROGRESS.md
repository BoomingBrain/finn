# FINN — Progress Log

Plan: [superpowers/plans/2026-10-28-finn.md](superpowers/plans/2026-10-28-finn.md) · Deadline: **Sun 1 Nov 2026**

## Status

| # | Task | Day | Status | Commit | Notes |
|---|---|---|---|---|---|
| 0 | Data spikes | Wed | ✅ Done | see log | NSE ✅, screener ✅, yfinance ✅, NVIDIA vision extraction 97% ✅, BSE API ❌. Cloud check from GitHub Actions ✅ |
| 1 | Foundation: models, snapshot store, LLM router, request budget | Wed | ✅ Done | see log | 3/3 budget tests; smoke: snapshot round trip, real cached NVIDIA call |
| 2 | Skeleton deploy: static site on HF Space, API on Render | Wed | 🟨 In progress | ae27f7e | Shell built and checked at 360/390 px; health API and CORS smoke OK; deploy dry run OK. Waiting: user OK to run `make deploy-space`; Render service setup |
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
| Wed 28 | Deployed shell opens on a phone; spikes recorded | ✅ Spikes done (cloud check deferred); deploy not attempted (local-only) |
| Thu 29 | Deployed Brief shows one real results card | |
| Fri 30 | Brief + Watch on all 18 stocks; lender cards; backtest sliders | |
| Sat 31 | 4 demo dossiers instant; unseen ticker streams or fails cleanly | |
| Sun 1 | Accuracy in README; submission sent | |

## Accuracy (filled by Task 14)

_Not run yet._

## Log

Newest first.

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
