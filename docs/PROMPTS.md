# FINN — Prompt Log

The requests that directed this build, in order, with what each produced. This is a **curated summary**: wording is
edited for clarity, and routine status checks and environment set-up exchanges are omitted. The unedited sessions
are in [build-history/](build-history/); the task-by-task engineering record is in [PROGRESS.md](PROGRESS.md).

## 1. Planning (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 1 | Write an implementation plan for FINN from the challenge brief. | 16-task plan with a Decisions section ([plan](superpowers/plans/2026-10-28-finn.md)). |
| 2 | Add a one-paragraph description to every task, and keep a progress log and a prompt log throughout. | Task descriptions and overview table; `PROGRESS.md` and this log. |
| 3 | Revise the plan against a 15-point review: vertical slice first, offline ingestion, cost guard, lender layout, code-judged guidance, an accuracy eval, event clustering, a schedule and a cut list (full text in the appendix). | Plan rewritten as Tasks 0–15 with nightly checkpoints. |

## 2. De-risking the data and the platform (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 4 | Before building anything, prove every data source works from where it will run: fetch real announcements, a screener.in page and a results PDF, save them as fixtures, and record what worked, what was blocked and the fallback chosen. | `docs/spikes.md`: NSE, screener.in, BSE files and yfinance confirmed; the BSE API blocked, so not used. Results-PDF extraction compared three ways; page-image vision won (97% vs 18% OCR). |
| 5 | Use NVIDIA's free model APIs instead of a paid provider, and pick a model per job. | One key; vision, bulk and reasoning tiers routed by job, with throttling, caching and a daily budget. |
| 6 | Host on a free tier: a Hugging Face Static Space for the app and Render for live research only; connect the GitHub repository. | Static site plus data on the Space; an API-only Render service; private repo with deploy scripts. |

## 3. Push: digest and alerts (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 7 | Build the foundation: data models, snapshot store, model router and a request budget. | Task 1. |
| 8 | Fetch and classify announcements into critical / notable / routine, rules first and a model only for leftovers. | Task 3: 92% classified by rules; one model call for the rest. |
| 9 | Turn a results PDF into Revenue / EBITDA / PBT / PAT with QoQ and YoY, refusing numbers that don't add up; handle banks and NBFCs. | Task 4: column selection, unit conversion, arithmetic checks and a high-resolution re-read; lender layout (NII / PPOP). |
| 10 | Ship one stock end to end, then scale to the whole portfolio with event clustering and management profiles. | Tasks 5–6: 18 holdings, results-day bundles folded into one event, profiles from the appointment filing. |
| 11 | Add price and volume alerts with user-set thresholds, shown with evidence of how often each would have fired. | Task 7: Watch with backtested sliders and an alert inbox. |
| 12 | Refresh the data on a schedule. | Task 8: GitHub Actions every 2 h on market days plus 19:00 IST. |

## 4. Pull: research dossiers (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 13 | Compute the financial snapshot deterministically from screener.in. | Task 9: growth, margins, returns, leverage, cash conversion and red flags, all in code. |
| 14 | Build Promised vs Delivered: the model only extracts targets; code decides the verdict. | Task 10: met / partly / missed / in progress / can't check, with grounded quotes. |
| 15 | Assemble cited dossiers and precompute the portfolio and demo set. | Task 11: citation guard, business section from the BRSR table, bull vs bear; 22 dossiers audited. |
| 16 | Serve research for any NSE ticker, with rate limits and a clear failure message. | Task 12: streaming API on Render. |
| 17 | Build the Ask screen and an "Ask about this" path from every Brief card. | Task 13. |
| 18 | Measure accuracy instead of assuming it, and cross-check every results card. | Task 14: 57/57 results fields, guidance recall 3/3 and precision 100%, 8/8 cards verified against screener.in. |
| 19 | Write the README, the submission draft and the build-history export. | Task 15. |

## 5. Product iterations (28–29 Oct)

| # | Request | Outcome |
|---|---|---|
| 20 | Save every live analysis permanently, keep the holdings' dossiers always present, and handle outdated information. | Live dossiers committed to the repo; a daily job rebuilds only when new results, a new concall or a new annual report appear; each dossier states what it covers. |
| 21 | Refresh only the holdings daily, not other companies. | The daily job is limited to the 18 holdings. |
| 22 | Add a Portfolio tab with every holding and a compact price chart. | Equal-weighted move, 1W / 1M / 3M range, price line against its starting price, biggest movers first. |
| 23 | List every instantly available company on the Ask screen. | Holdings and other researched companies, updated automatically as dossiers are saved. |
| 24 | Show a progress bar that reflects the real work. | The server reports completed steps; the bar never estimates. |
| 25 | Lift the 3-per-hour limit, queue concurrent requests and notify the user when an analysis is ready. | 20 per hour; at most 2 builds at once with queue position; shared builds; in-app banner and system notification. |
| 26 | Move the Watch settings to the top as a compact, expandable summary. | The alert rule as threshold boxes; tap to edit in place. |
| 27 | Polish the whole interface: less text, information in compact boxes, colour-coded numbers. | Stat boxes for every number group, threshold-coloured ratios, clamped non-AI text, compact citations. |
| 28 | Find out how to make live research faster, test whether more models can share the slow step, and plan the work. | Measured the bottleneck; tested 7 models (none qualified); plan for passage-level extraction, a parallel annual report and a nightly Nifty 50 prebuild ([plan](superpowers/plans/2026-10-29-faster-live-research.md)), executed task by task. |
| 29 | Make scheduling robust using GitHub Actions only. | Schedules moved off the top of the hour; a watchdog workflow starts any job that's overdue. |
| 30 | Add a chat section that answers questions about the holdings and researched companies only, says "research pending" for anything else, and uses retrieval over the researched content only. | Chat tab over an embedded index of every report's cited passages; uncited, off-topic and unresearched questions handled without inventing answers. |
| 31 | Stop prebuilding the Nifty 50; research other companies only when asked. | Prebuild job and its company list removed, and the watchdog no longer restarts it. Live research results are still saved permanently. |
| 32 | Add a Gemini API key as a fallback model. | NVIDIA first; on failure the same prompt goes to `gemini-3.5-flash`, which scored 57/57 on the results eval. The free tier is 20 requests a day, so it rescues single calls. |
| 33 | Live research works while the app is on screen but fails after switching away. | Two causes: the browser cut the stream and the app gave up, and Render's free tier stopped the idle server mid-build. The app now rejoins the build when the screen returns, and the server keeps itself awake while a build runs. |

## Appendix: full text of the plan review


```
Revise the existing FINN implementation plan (the .md plan file) based on the
review below. Do not start coding. Update the plan file in place, keep its
current format (Decisions, Global Constraints, Review Focus, Tasks with
interfaces and TDD steps), and give me a short summary of what changed.

Context: deadline is Sun 1 Nov 2026, it is Wed 28 Oct. The brief grades
product sense, judgment and architecture, and says a thin working prototype
beats a broad broken one. Making the demo run reliably matters most.

CHANGES TO MAKE

1. Add "Task 0: Data spikes (first 1-2 hours)". Throwaway scripts that prove,
   before anything else is built:
   - NSE announcements fetch works for 3 stocks; if NSE blocks scripts, test
     the BSE announcements feed and make that the primary source.
   - One screener.in company page parses (quarters table, annual report and
     transcript links); note whether it needs a login or rate limits.
   - One real results PDF yields Revenue, EBITDA, PBT, PAT for current
     quarter, previous quarter and year-ago.
   Save every real response as a test fixture. If a source fails, record the
   fallback chosen. Later tasks must use what Task 0 actually found.

2. Reorder into a vertical slice. New order: Task 0 spikes, then minimal
   foundation (models, store, llm), then one stock end-to-end (announcement ->
   classify -> results card -> Brief screen) DEPLOYED by Thursday night, then
   widen to all 18 stocks, alerts, then Pull, then Ask UI, then polish. Move
   deployment of a skeleton to Day 1 instead of the last task.

3. Cut test volume. Keep TDD only for logic that can silently be wrong:
   compute_results, signal detection, classify rules, drop_uncited, metrics,
   delivery verdict logic. Replace the rest and most UI tests with smoke
   checks. Say in the plan which tests were dropped and why.

4. Data access from the cloud. Assume NSE and screener.in may block cloud
   server IPs. Change the design so ingestion (announcements, prices, PDFs,
   screener data) runs from my machine or GitHub Actions and commits/uploads
   snapshots; the deployed app serves saved data. Pre-compute dossiers for
   the demo tickers. For an unseen ticker, try live fetch and, on failure,
   show a clear "couldn't fetch sources for this ticker from the server"
   message instead of crashing.

5. Hosting. Free Render services sleep and lose disk, so replace SQLite-on-disk
   assumptions. Prefer ONE deployed service that serves both the API and the
   built web app, with the cache held in committed JSON/seed files or a free
   hosted database. Remove the three-platform setup (Render + Vercel + Actions
   cron hitting an API) unless you justify it.

6. Cost safety. Add a daily LLM spend cap and per-IP rate limit on any endpoint
   that can trigger model calls. Serve cached dossiers without limits.

7. Bank and lender handling in the Push results card. HDFCBANK and BAJFINANCE
   are in the portfolio. Add a layout detection step: for banks/NBFCs show net
   interest income and PAT (and PPOP if present) instead of EBITDA, or mark
   EBITDA "not applicable". Add tests for this.

8. Promised vs Delivered: stop letting the LLM judge delivery. The model
   should extract each target as structured data (metric, comparison, value,
   period, quote, source id). Compute the actual from the quarterly table in
   code and compute the verdict (met / partly / missed / pending) in code. The
   model only writes the one-line explanation. Update the interfaces and tests.

9. Accuracy check. Add a small eval script: hand-verify 5 real results PDFs
   and 3 transcripts, record expected numbers in a fixtures file, run the real
   extraction, and output accuracy. Also cross-check extracted quarterly
   figures against the screener quarterly table and flag mismatches on the
   card as "unverified". Handle half-year and full-year columns in Q2/Q4
   filings so the quarter columns are chosen correctly. Put the accuracy
   numbers in the README writeup.

10. De-noise the Brief. Cluster related filings for the same company and day
    (board outcome, results, presentation, newspaper ad) into one event card
    that links all documents. Show that day's price move on the card. Add
    tests for the clustering.

11. Interaction model. Keep the 3-tab shell but add a point of view:
    - "Ask about this" on every Brief card, opening Ask with context.
    - Swipe-to-dismiss triage on cards.
    - Threshold sliders that show "would have fired N times in the last 30
      days" using stored price history.
    - Ask accepts a natural question, not just a ticker (e.g. "did X hit its
      margin target?"), answered only from the cited dossier.
    Build the two cheapest of these first and list the rest as next steps.

12. Management change cards: if the filing has no profile section, show "No
    profile in filing" and link the filing. Say in Decisions that LinkedIn
    scraping was avoided and why.

13. Primary-source note. screener.in tables are used for numbers; state in
    Decisions that they are standardised from company filings, and that
    guidance and narrative come only from transcripts and annual reports.

14. Add a day-by-day schedule at the top of the plan (Wed to Sun) with a
    "demo must work" checkpoint each night, and a cut list: what to drop
    first if time runs out (order: Watch notifications polish, bull/bear,
    business snapshot, extra UI tests).

15. Keep my AI build history exportable: note in the README task that all
    Claude Code sessions must be kept and linked in the submission.

Keep everything that was good: tiers, caching, rules-before-LLM, citation
guard, stale/empty/unreadable states, seed fallback, model routing.
```
