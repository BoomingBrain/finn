# FINN — Prompt Log

Every prompt given to the coding agent while building FINN, in order, with a one-line note on what it produced. This is part of the "AI build history" deliverable. Prompts are verbatim; slash commands are shown as typed.

| # | Date | Prompt | Outcome |
|---|---|---|---|
| 1 | 2026-10-28 | `/plugin marketplace add obra/superpowers-marketplace` | Not available in this environment (VS Code extension). |
| 2 | 2026-10-28 | `/plugin install frontend-design@claude-plugins-official` | Not available in this environment. |
| 3 | 2026-10-28 | `/superpowers:writing-plans` | Read both challenge PDFs and wrote the 16-task plan `docs/superpowers/plans/2026-10-28-finn.md`, with a Decisions section in place of a design doc. |
| 4 | 2026-10-28 | "also add a brief description of the each task in md and i want you to maintain a progress log and my prompt log somewhere" | Added per-task descriptions and an overview table to the plan; created `docs/PROGRESS.md` and this file. |
| 5 | 2026-10-28 | Plan review with 15 requested changes (full text below) | Rewrote the plan: Tasks 0–15, vertical slice, offline ingestion + one HF Spaces service, cost guard, lender layout, code-judged guidance, eval, clustering, schedule + cut list. |
| 6 | 2026-10-28 | "Before anything is built, prove that every data source works from where it will actually run. Throwaway scripts fetch real announcements, a real screener.in page and a real results PDF, save each response as a test fixture, and record in `docs/spikes.md` what worked, what was blocked and which fallback was chosen" | Ran Task 0 (data spikes). |
| 7 | 2026-10-28 | Request to cut `/usage` costs of the superpowers plugin and writing-plans skill (interrupted by the user before any action) | Not acted on. |
| 8 | 2026-10-28 | "task 0 done?" | Status report: Task 0 committed (247448d); 2 checks pending. |
| 9 | 2026-10-28 | "complete task 0" | Ran the two pending Task 0 checks. |
## Full text of long prompts

### #5 — Plan review (2026-10-28)

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
