# FINN — Prompt Log

Every request I gave the coding agent while building FINN, in order, with what each one produced. **The wording here is edited for clarity and tone, and it is not verbatim.** My requests about the format of this log itself are left out. The exact, unedited sessions are in [build-history/](build-history/), and the task-by-task engineering record is in [PROGRESS.md](PROGRESS.md).

## 1. Planning and environment (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 1 | Set up the development environment: install the Superpowers, Context7 and frontend-design plugins for Claude Code. | Plugins installed and active. |
| 2 | Write an implementation plan for FINN from the challenge brief. | 16-task plan with a Decisions section ([plan](superpowers/plans/2026-10-28-finn.md)). |
| 3 | Add a short description to every task, and keep a progress log and a prompt log throughout. | Task descriptions and an overview table; `PROGRESS.md` and this log. |
| 4 | Revise the plan against a 15-point review: vertical slice first, offline ingestion, cost guard, lender layout, code-judged guidance, an accuracy eval, event clustering, a schedule and a cut list (full text in the appendix). | Plan rewritten as Tasks 0–15. |
| 5 | Review the tool-usage report and reduce the overhead of the planning skill and plugins, showing each change first. | Reviewed; no changes made. |

## 2. De-risking the data and the platform (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 6 | Before building anything, prove every data source works from where it will run: fetch real announcements, a screener.in page and a results PDF, save them as fixtures, and record what worked, what was blocked and the fallback chosen. | `docs/spikes.md`: NSE works with cookies, BSE is blocked, screener.in works, and results PDFs need a vision model. |
| 7 | Confirm the status of Task 0 and complete it. Keep everything local for now and leave GitHub repository creation for later. | Task 0 finished locally. |
| 8 | Report the outcome of Task 0: does every call and data retrieval work? | Call-by-call results; every data type has a working route. |
| 9 | Use NVIDIA's free model APIs instead of a paid provider, and recommend the models. | Model candidates compared on the free catalog. |
| 10 | List the models we will use, and confirm whether they need one API key or several. | One key covers all of them. |
| 11 | I've added the API key. Verify it and complete Task 0. | Spike re-run with the key; vision, bulk and reasoning tiers chosen on measured results. |
| 12 | Build the foundation: shared data models, the snapshot store, the portfolio list, and one model gateway with routing, throttling, caching and a daily budget. | Task 1. |
| 13 | Take the public-URL deployment option, and tell me what it requires. Advise on Hugging Face Space types, given that Docker is paid and the alternatives are static or Gradio. | Static Space chosen for the app and data. |
| 14 | I've added the Hugging Face token. Where do I find the Space identifier? | Space configured. |
| 15 | Add a free Render service for live research, and walk me through setting up it and the push permission. | Render API service; step-by-step set-up guide. |
| 16 | Connect the GitHub repository (BoomingBrain/finn). | Remote added; private repository. |
| 17 | Confirm the Hugging Face deployment is correct and advise on next steps. Move to the next task once the earlier ones are complete, and give me detailed instructions for anything I need to do myself. | Deployment verified; set-up steps provided. |
| 18 | The set-up steps are done. Deploy it. | Task 2 live: a skeleton app on the Space and the API on Render. |

## 3. Push: digest and alerts (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 19 | Fetch announcements and classify them as critical, notable or routine, with rules first and a model only for leftovers. | Task 3: about 92% classified by rules. |
| 20 | Turn a results PDF into Revenue / EBITDA / PBT / PAT with QoQ and YoY, refusing numbers that don't add up, and handle banks and NBFCs. | Task 4: column selection, unit conversion, arithmetic checks and a high-resolution re-read; lender layout (NII / PPOP). |
| 21 | The Render link shows nothing. Please check it. | Confirmed working: Render is the API only, and the app is opened from the Space. |
| 22 | Ship one stock end to end: an ingest command writes the snapshot, and the deployed Brief shows its real results card on a phone with window chips, tiers and empty and stale states. | Task 5: INFY live on the Brief. |
| 23 | Scale to the whole portfolio. Fold results-day filings into one event, and give management changes the appointee's profile from the filing. | Task 6: 18 holdings, event clustering and profiles. |
| 24 | Add price and volume alerts with user-set thresholds, with sliders showing how often each setting would have fired over 30 days. | Task 7: Watch tab and an alert inbox. |
| 25 | Proceed to scheduled refreshes, using the option where you add the repository secrets. I've added all of them on GitHub. | Task 8: GitHub Actions every 2 h on market days plus an evening run. |

## 4. Pull: research dossiers (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 26 | Proceed to the financial snapshot, computed deterministically from screener.in. | Task 9: growth, margins, returns, leverage, cash conversion and red flags, all in code. |
| 27 | Build Promised vs Delivered: the model only extracts targets, and code decides the verdict. | Task 10: met / partly / missed / in progress / can't check, with grounded quotes. |
| 28 | Continue with the remaining research tasks: cited dossiers, the precomputed set, the live API and the Ask screen. | Tasks 11–13: citation guard, business section, bull vs bear, streaming API on Render. |
| 29 | The Ask engine isn't live on the site yet. Please check. | Space redeployed; Ask live for any NSE ticker. |
| 30 | Finish the unfinished tasks in the plan. | Task 14 (accuracy: 57/57 results fields, guidance recall 3/3) and Task 15 (README, submission draft, history export). |

## 5. Product iterations (28 Oct)

| # | Request | Outcome |
|---|---|---|
| 31 | Explain which companies open instantly, how a new company's analysis works and how long it takes. | Explained the precomputed set and the live path. |
| 32 | Save every generated analysis permanently, keep the holdings' dossiers always present, and explain how outdated information is handled. | Live dossiers committed to the repo; a daily job rebuilds when new results, a new call or a new annual report appear; each dossier states what it covers. |
| 33 | The GitHub token is added. How much of the report generation remains? | Remaining precompute work reported. |
| 34 | Add a Portfolio tab showing every holding and its movement as a compact chart. | Equal-weighted move, 1W / 1M / 3M range, biggest movers first. |
| 35 | List every instantly available company on the Ask screen. | Holdings and other researched companies, updated as dossiers are saved. |
| 36 | Give me status updates on the running report generation until it completes. | Progress reported until the build finished. |
| 37 | Confirm that selecting a new company produces a complete new analysis. | Confirmed the live flow. |
| 38 | Add a progress bar that reflects the real work being done. | The server reports completed steps; the bar never estimates. |
| 39 | Explain how to get past the limit of 3 requests per hour. Then raise it, queue concurrent requests, and notify the user when an analysis is ready. | 20 per hour; at most 2 builds at once with queue position; shared builds; in-app banner and system notification. |
| 40 | Does the daily job update every report? It should check only the holdings, not other companies. | The daily job is limited to the 18 holdings. |
| 41 | How can new research be made faster? Can several models share the bottleneck step? | Bottleneck measured; 7 models tested and none qualified, so the job stays on the reasoning model. |
| 42 | Confirm whether all of that work is complete. | Status reported. |

## 6. Interface, speed and scheduling (29 Oct)

| # | Request | Outcome |
|---|---|---|
| 43 | What work remains? | Remaining items listed. |
| 44 | Polish the Watch alerts: move the settings from the bottom to a compact summary at the top that expands for editing. | The alert rule as threshold boxes; tap to edit in place. |
| 45 | Polish the whole interface: remove unnecessary text, present non-AI information in concise boxes, colour-code numbers, and keep it clean and crisp. | Stat boxes for every number group, threshold-coloured ratios, clamped text, compact citations. |
| 46 | Write a plan to make live research faster. | Plan for passage-level extraction, a parallel annual report and a nightly Nifty 50 prebuild ([plan](superpowers/plans/2026-10-29-faster-live-research.md)). |
| 47 | The plan looks good. Execute it natively, task by task. | Parallel read kept; passage-level extraction reverted because it failed the accuracy gate. |
| 48 | Produce a proper architecture diagram as a PNG, explaining the system in detail. | `docs/architecture.png`, linked from the README. |
| 49 | How many tasks remain, and what is running now? | Status reported. |
| 50 | Evaluate caching all Nifty 50 companies for faster results. | Trade-offs presented. |
| 51 | My concern is that caching everything sacrifices freshness. | Discussed; the prebuild continued for the time being. |
| 52 | Could a Gemini API key help, given its speed? I have a Gemini Pro plan. | Pro covers the Gemini app, not API quota. |
| 53 | What is running in the background? | Reported, and flagged that GitHub was skipping scheduled runs. |
| 54 | Agreed, let's fix the unreliable schedule, using GitHub cron only and making it robust. | Schedules moved off the top of the hour; a watchdog workflow starts any overdue job. |
| 55 | Make the product more interactive. Brainstorm and plan ideas: acting on an item, asking in my own words, changing the portfolio, comparing companies. | Options reviewed; narrowed to chat. |
| 56 | Add only a Chat section. It answers on the holdings and researched companies, says "research pending" for anything else, and uses a RAG system over researched content. Retrieve from the reports only. | [Design](superpowers/specs/2026-10-29-chat-design.md) and [plan](superpowers/plans/2026-10-29-chat.md) written. |
| 57 | Design approved, and plan approved. | Chat tab over an embedded index of every report's cited passages, with hybrid search, a relevance gate and no uncited sentences. |
| 58 | What is the Nifty 50 prebuild, and how much of it is done? | Explained, with progress reported. |
| 59 | Stop prebuilding. Research other companies only when asked. | Prebuild job and its list removed; the watchdog no longer restarts it. |

## 7. Reliability and final checks (30 Oct – 1 Nov)

| # | Request | Outcome |
|---|---|---|
| 60 | What's left now? | Remaining work listed, with live builds on Render as the main open issue. |
| 61 | Add Gemini API keys as a fallback model, on the free tier. | NVIDIA first; a failed call goes to `gemini-3.5-flash`, which scored 57/57 on the results eval. The free tier is 20 requests a day, so it rescues single calls. |
| 62 | I've added the key on GitHub. I've also noticed live research works best while the app is on screen, and fails after switching away. Please investigate. | Two causes fixed: the app gave up when the browser cut the stream (it now rejoins the build), and Render's free tier could stop an idle server (it now pings itself during a build). |
| 63 | Is everything complete? | Not yet: the no-viewer test hadn't finished. |
| 64 | Confirm that everything is complete. | The no-viewer test had failed, so I had it rerun with a viewer attached, which succeeded in 136 seconds, and then tested a new company with no viewer: TVS Motor finished and saved in 13 minutes. |
| 65 | Include the project's architecture in the README, with proper flowcharts. | Architecture image updated; Mermaid flowcharts added for the system, scheduled ingest, live research and Chat. |

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
