# Submission email (draft — send from your own account)

**To:** assessment@enam.com
**Subject:** ENAM - IIT screening - 2027

---

Hello,

Here is my submission for the AI Engineer Build Challenge: FINN, a financial investment agent that tells you less.

**Links**
- Prototype (open on a phone): https://ayush-rai-230265-finn.static.hf.space
- Repository: https://github.com/BoomingBrain/finn
- AI build history: https://github.com/BoomingBrain/finn/tree/main/FINN_BUILD_HISTORY_EXPORT (a written account of the build, plus the exact Claude Code sessions, readable and raw, in `source_sessions/`), plus a curated account of every request and its outcome in [PROMPTS.md](https://github.com/BoomingBrain/finn/blob/main/FINN_BUILD_HISTORY_EXPORT/PROMPTS.md) and the task-by-task log in [docs/PROGRESS.md](https://github.com/BoomingBrain/finn/blob/main/docs/PROGRESS.md)

**What I built.** A mobile web app with five tabs over an 18-stock portfolio:
- **Brief:** a windowed digest of every exchange filing, sorted into critical, notable and routine. Results filings get a Revenue / EBITDA / PBT / PAT card with QoQ and YoY; management changes get the incoming person's profile.
- **Portfolio:** every holding with a compact price chart, biggest movers first.
- **Watch:** alerts on thresholds you set, each slider showing how often it would have fired over the last 30 days.
- **Ask:** a research dossier on any NSE ticker. It covers a financial snapshot, Promised vs Delivered across the last four earnings calls, the business, and bull vs bear, with every claim linked to the exact PDF page.
- **Chat:** questions in your own words about the holdings and researched companies, answered only from FINN's reports, with every sentence cited. A company without a report gets "Research pending".

**Key decisions and trade-offs**
- **The model reads, the code decides.** LLMs only extract numbers and quotes; code computes every figure and verdict.
  - Results must pass the statement's own arithmetic or are shown as unreadable instead of wrong. They are also cross-checked against screener.in.
  - In Promised vs Delivered, code rules met, partly or missed against the reported quarters, and the model only explains a verdict it can't change.
- **No claim without a page.** Every model-written sentence must cite a page FINN sent it, or it is dropped.
- **Routing by evidence.** I tested before choosing:
  - **Vision for results tables:** a vision model scored 97% on real results PDFs, against 18% for OCR text.
  - **A large reasoning model only for guidance and bull vs bear:** a small model mislabelled past results as targets.
  - **Rules first:** they classify about 92% of filings before any model runs.
  - **Cost:** everything runs on NVIDIA's free tier, so the total is ₹0.
- **Static-first architecture.** Scheduled ingestion on GitHub Actions commits JSON snapshots that a static site serves, so viewers cost nothing and the demo can't go down. A small server exists only for Chat and for live research on tickers outside the precomputed set, rate-limited and budget-capped.
- **Measured accuracy.** On a hand-checked gold set:
  - **Results:** 57/57 fields correct across a bank, an NBFC, a Q4 filing and a ₹-million filing.
  - **Guidance:** recall 3/3, precision 100%.
  - **Live cards:** 8/8 agree with screener.in.

**What I deliberately left out**
- **Balance-sheet deep-dive and annual-report narrative analysis:** Promised vs Delivered does the "analyse, don't summarise" job more rigorously.
- **LinkedIn bios:** the appointment filing is a primary source that always carries a profile.
- **Web push and real-time feeds:** the data is end-of-day.
- **Acting on items, editing the portfolio, comparison views:** I considered these for interactivity and built only Chat, which reaches furthest with one new surface.

**Known limitations**
- A new company's live research takes about 13 minutes on the free tier. The app can be left during a build: one no-viewer test finished and saved, and an earlier one didn't, for a reason I couldn't establish. Asking again restarts a lost build.
- A company that far beats an "approximately" target is currently marked missed, because the rule needs a direction.

**Where I'd take it next**
1. Swipe-to-triage on the Brief that teaches the tier rules.
2. Web push for critical alerts.
3. A real-time exchange feed.
4. Per-investor accounts.

Thank you for the interesting problem.

Ayush Rai

---

Before sending:
- [ ] Give the reviewers access to the repo: make `BoomingBrain/finn` public, or add them as collaborators. It is private now, so these links would 404 for them.
- [ ] Open the prototype on a phone once (the free Render server sleeps; the first live-research request wakes it in about a minute).
