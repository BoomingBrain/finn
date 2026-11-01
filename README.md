# FINN — a financial investment agent that tells you less

**Try it on a phone:** https://ayush-rai-230265-finn.static.hf.space

FINN is a mobile-first web app for an investor who holds 18 Indian stocks. It has five tabs:

- **Brief:** what changed across the portfolio in a time window you choose, with the few things that matter on top and everything routine collapsed.
- **Portfolio:** every holding with a compact price chart, biggest movers first.
- **Watch:** alerts on the thresholds *you* set: filing types you care about, volume spikes, price moves. Each slider shows how often it would have fired over the last 30 days.
- **Ask:** a research dossier on any NSE company, built only from its own filings, annual report and earnings-call transcripts, with every claim linked to the exact PDF page.
- **Chat:** questions in your own words about your holdings and researched companies, answered only from FINN's reports, each sentence cited.

## Point of view

The scarce skill is not collecting information but deciding what to ignore, so FINN makes that decision explicit and checkable:

- **Every filing gets one of three tiers.** Critical items get a rich card, notable items a one-line summary, routine items a collapsed count. The tier rules are code you can read (`backend/finn/push/classify.py`), not a model's mood. For example, a subsidiary's incorporation or an NCD allotment is filed as "M&A" or "fund raise" but is housekeeping, so it is not critical.
- **The model reads, the code decides.** LLMs extract numbers and quotes; code computes every figure, verdict and threshold. Results cards must pass the statement's own arithmetic (PBT − tax = PAT, and so on) or they are marked unreadable rather than shown wrong. They are also cross-checked against screener.in's reported quarter.
- **Analyse management, don't summarise it.** The research view leads with *Promised vs Delivered*:
  - The model pulls each explicit numeric target out of the last four concall transcripts.
  - Code measures what the reported quarters actually delivered and rules met, partly, missed, in progress, or can't check.
  - The model then writes one line explaining a verdict it cannot change.
- **No claim without a page.** Every model-written sentence must cite a source page FINN actually sent it, or it is dropped. The citation chips open the PDF at that page.

## What's in it

**Push**
- **Windowed digest** (24 h / 7 d / 30 d), prioritised by tier. Filings about the same thing within 36 h (results + press release + newspaper ad + auditor's report) fold into one event.
- **Results cards:** Revenue, EBITDA, PBT and PAT, this quarter vs QoQ and YoY.
  - Read from the statement page image by a vision model, with column selection and unit conversion (₹ crore / lakh / million) done in code.
  - Lenders automatically get NII / PPOP / PBT / PAT, since EBITDA is meaningless for a bank.
  - A card that fails its arithmetic gets one 200-dpi re-read, else "Couldn't read the numbers — open filing".
- **Management changes:** a profile of the incoming person (role, background, prior roles) taken from the appointment filing itself, which SEBI requires to include one. Scanned filings are read as images.
- **Other material filings** get a one-line summary; routine ones get none.
- **Price reaction** on the first trading session after each event.
- **Alerts:**
  - per-category toggles
  - volume ≥ N× its 20-day average, and price moves beyond ±X%
  - the badge and inbox update on the scheduled refresh

**Pull (any NSE ticker)**
1. **Financial snapshot:** last-four-quarter revenue and profit, 3-year growth, margins (computed from rows, not screener's rounded column), ROCE/ROE, debt-to-equity, cash conversion (CFO ÷ PAT), eight-quarter sparklines, and plain-English red flags. A missing number shows as "—", never 0.
2. **Promised vs delivered:** as above. For example, Pidilite: "20–24% EBITDA margin corridor" for FY26 was **met** at 24.1%, and FY27 is **in progress** at 26.2% after one quarter.
3. **The business:** what it sells and to whom, plus segments with their share of turnover. Shares come from the annual report's BRSR "business activities" table and are blanked unless printed on the cited page.
4. **Bull vs bear:** at most three cited points each side, from the stronger reasoning model.

**Chat (holdings and researched companies)**
- **Ask in your own words:** "Is Polycab's debt a concern?", "Which holdings missed guidance?", "Compare margins of Infosys and Persistent".
- **Retrieval over FINN's reports only.** Every report is split into small cited passages and embedded with NVIDIA's embedding model. A question is matched by meaning and keywords, and the fast model answers in at most 5 sentences, each citing a passage, so uncited sentences are dropped.
- **Unknown companies:** a question naming a company without a report gets "Research pending for {name}", with a link to research it.
- **Off-topic questions** (measured by how close they come to anything researched) get "The reports don't cover that", with no model call.
- **Follow-ups** ("what about its margins?") keep the previous question's companies.

Four demo tickers (PIDILITIND, HAL, CDSL, NAUKRI) and all 18 holdings are precomputed and open instantly. Any other ticker is researched live on the server, and its sections stream in as they finish.

**Every dossier is built once and kept current:**
- **Saved permanently.** A finished live dossier is committed to the repo next to the precomputed ones (`finn/persist.py`). The server replays it from there instead of rebuilding, and the next deploy makes it a static, instant page. A dossier with a failed section is never saved.
- **Holdings always present and current.** A daily job (`.github/workflows/dossiers.yml`, 20:17 IST) checks the 18 holdings only:
  - builds any missing dossier and retries any with a failed section
  - rebuilds a dossier when its inputs changed: each one records the latest results quarter, concall and annual report it used, and the job compares that with screener.in (no model calls)
  - older transcripts come from the LLM cache, so a rebuild pays only for what is new
- **Other companies are not refreshed.** Demo tickers and companies researched live keep the dossier as built.
- **Freshness is visible.** Each dossier says what it covers: "Covers results to Sep 2026, the Aug 2026 call and the FY26 annual report. Updated 28 Oct 2026."

## Architecture

![FINN architecture: sources, scheduled jobs, model gateway, repository, static app and live research service](docs/architecture.png)

The diagram's source is [docs/architecture/architecture.html](docs/architecture/architecture.html); re-render with headless Chrome at 1800×1340, scale 2. The flowcharts below show the same system as flows.

### System overview

Scheduled jobs publish static data, so opening the app costs nothing. A small server handles only what can't be precomputed.

```mermaid
flowchart LR
  subgraph SRC["Primary sources"]
    NSE["NSE announcements"]
    YF["Yahoo Finance prices"]
    SCR["screener.in financials"]
    PDF["Results PDFs, call transcripts, annual reports"]
  end

  subgraph GHA["GitHub Actions"]
    ING["Ingest<br/>every 2 h on market days, 19:11 IST"]
    DOS["Refresh holdings' research<br/>20:17 IST"]
    WD["Watchdog, every 30 min<br/>starts overdue jobs"]
  end

  GW["Model gateway<br/>routing, cache, throttle, budget"]
  NV["NVIDIA free tier<br/>vision, fast, reasoning, embeddings"]
  GEM["Gemini free tier<br/>fallback for failed calls"]
  REPO[("GitHub repository<br/>data/snapshot/")]
  SPACE["Hugging Face Static Space<br/>app + data"]
  API["Render FastAPI<br/>live research + Chat"]
  USER(["Investor's phone"])

  SRC --> ING
  SRC --> DOS
  WD -.-> ING
  WD -.-> DOS
  ING --> GW
  DOS --> GW
  API --> GW
  GW --> NV
  GW -.->|on failure| GEM
  ING --> REPO
  DOS --> REPO
  REPO -->|deploy| SPACE
  SPACE -->|"Brief, Portfolio, Watch, ready reports"| USER
  USER <-->|"new company, Chat"| API
  SRC --> API
  API -->|save finished report| REPO
  SPACE -->|chat index| API
```

### Scheduled ingest

Rules and code do most of the work. A model is called only where they can't decide, and its answer is cached.

```mermaid
flowchart TD
  A["Fetch new filings and closing prices"] --> B{"Do the rules<br/>classify it?"}
  B -->|"yes, about 92%"| C["Critical, notable or routine"]
  B -->|no| B2["Fast model picks the category"] --> C
  C --> D{"Which tier and type?"}
  D -->|results| E["Vision model reads the statement page"]
  D -->|management change| F["Profile from the appointment filing"]
  D -->|other notable| G["One-line summary"]
  D -->|routine| H["No model call"]
  E --> I{"Does the<br/>arithmetic hold?"}
  I -->|yes| J["Results card, cross-checked against screener.in"]
  I -->|no| K["One 200-dpi re-read"]
  K --> L{"Holds now?"}
  L -->|yes| J
  L -->|no| M["Shown as unreadable, with a link to the filing"]
  J --> N["Cluster filings within 36 h into one event"]
  M --> N
  F --> N
  G --> N
  H --> N
  N --> O["Compute price and volume signals"]
  O --> P["Commit the snapshot and deploy the Space"]
```

### Live research on a new company

```mermaid
flowchart TD
  A(["Investor picks a company"]) --> B{"Report already<br/>published?"}
  B -->|yes| C(["Opens instantly"])
  B -->|no| D{"Saved on the server,<br/>or building now?"}
  D -->|saved| E(["Replayed from the saved report"])
  D -->|building| F["Join that build and replay its progress"]
  D -->|neither| G{"Real NSE symbol,<br/>within limits?"}
  G -->|no| H(["Fixed message: unknown symbol or limit reached"])
  G -->|yes| I["Queue, at most 2 builds at once"]
  I --> J["Financial snapshot, computed in code"]
  J --> K["Read the last 4 calls:<br/>reasoning model extracts targets"]
  J --> L["Read the annual report:<br/>fast model writes the business section"]
  K --> M["Code rules met, partly, missed,<br/>in progress or can't check"]
  L --> N["Bull vs bear, reasoning model"]
  M --> N
  N --> O["Drop any sentence without a valid citation"]
  O --> P["Save the report to GitHub"]
  P --> Q(["Done: banner or notification"])
  F --> J
  J -.->|"each step streams to the app"| R["Progress bar and sections"]
  R -.->|"connection cut when the app leaves the screen"| S["Rejoin when the screen returns"]
  S -.-> F
```

### Chat

```mermaid
flowchart TD
  A(["Investor asks a question"]) --> B{"Within the<br/>limits?"}
  B -->|no| C(["Fixed message, no model call"])
  B -->|yes| D["Find the companies named,<br/>or carry them over from the last question"]
  D --> E{"Named company<br/>has no report?"}
  E -->|"none of them do"| F(["Research pending for that company,<br/>with a link to research it"])
  E -->|no, or some do| G{"Close to anything researched?<br/>No company named and best match under 0.25 means no"}
  G -->|no| H(["The reports don't cover that"])
  G -->|yes| I["Hybrid search over report passages:<br/>0.6 meaning + 0.4 keywords, top 12"]
  I --> J["Fast model answers from those passages only"]
  J --> K["Drop any sentence without a valid citation"]
  K --> L{"Anything left?"}
  L -->|no| H
  L -->|yes| M(["Answer with chips that open the cited page"])
```

### Design notes

- **Viewers cost nothing.** Brief and Watch, and every precomputed dossier, are static files, so a viewer triggers no model call.
- **Ingestion is incremental and cached.** Each filing is classified and enriched once, and every model response is cached in SQLite by its exact input.
- **Live research is queued and guarded:**
  - an unknown ticker gets a 404 before any work
  - at most 2 analyses build at once, and the rest wait in line with their position shown
  - a second request for a company already building joins that build
  - builds keep running if the viewer leaves, and the app shows a banner (or a system notification, if allowed) when one finishes
  - up to 20 new analyses per IP an hour, plus a daily request budget
  - a real progress bar counts completed steps
  - if screener.in can't be reached, the user gets a clear message, not a crash

## Models and cost

The NVIDIA API catalog's free tier, one key, each tier routed to the job it fits:

| Tier | Model | Used for |
|---|---|---|
| vision | `nemotron-3.5-super-vl-120b-a12b` | Results statement pages, scanned management filings |
| bulk | `nemotron-3.5-lightning-30b-a3b` (thinking off) | Leftover classification, one-line summaries, profiles, business section, verdict explanations |
| reason | `nemotron-3-ultra-550b-a55b` (thinking on) | Guidance extraction, bull vs bear |

**Fallback:** when NVIDIA still fails after its retries, the same prompt goes to Google's `gemini-3.5-flash` (free tier, optional `GEMINI_API_KEY`).
- With every call forced onto it, it scored 57/57 on results extraction.
- The free tier allows 20 requests a day, so it rescues individual failed calls, not whole builds.

**Choices made on evidence, not by default:**
- **Results go to the vision model.** On real filings it scored 97% vs 18% for OCR text and 3% for a document parser (`docs/spikes.md`).
- **Guidance went to the reasoning model.** The bulk model mislabelled past results and volume growth as revenue targets; the reasoning model returned only the real one.
- **Rules classify about 92% of filings** before any model is called.

**Cost: ₹0.**
- The first 22 precomputed dossiers, with all development and ingestion up to that point, took 465 model calls (154 bulk, 20 vision, 291 reason) on the free tier.
- A viewer of the deployed app costs nothing.
- The reasoning tier is capped at 2 calls in flight to stay inside the free rate limit.

## Accuracy

`make eval` scores extraction against gold values I read by hand from the rendered PDF pages (`backend/eval/`):

| | Gold set | Score |
|---|---|---|
| **Results fields** (within 0.5%) | 5 filings: INFY, HDFCBANK (bank), BAJFINANCE (NBFC), PIDILITIND Q4 (with full-year columns), POLYCAB (₹ million) | **57/57** |
| **Guidance targets** (metric + period + value) | 3 calls: PIDILITIND, HAL, CDSL (CDSL has none, which tests precision) | **recall 3/3, precision 100%** |
| **Live results cards vs screener.in** (2% tolerance) | every card in the current snapshot | **8/8 verified** |

The gold set is small, so read this as "no known errors on a deliberately varied sample", not as a population rate.

## Known limitations

- **Live research is free-tier infrastructure.** A new company took 13 minutes on the last full test, and the first request after the server has slept takes about a minute longer.
- **Leaving the screen:** tested twice with the viewer gone. TVS Motor finished and saved in 13 minutes; an earlier Maruti run never saved, for a reason I couldn't establish, and the same company then finished normally with a viewer attached. If a build is lost, asking again restarts it.
- **The keep-awake ping is untested past Render's 15-minute idle limit,** since the successful run finished inside it.
- **Gemini fallback:** the free tier allows 20 requests a day. It scored 57/57 on results extraction, but the quota ran out before the guidance eval, so its guidance accuracy is unmeasured.
- **"Approximately" targets:** a company that far beats one is marked missed (L&T's margin was 12.6% against about 8.5%). The rule treats it as a band and needs a direction.

## Testing

- **Coverage:** 260 backend tests (pytest) and 40 web tests (Vitest).
- **Where the tests sit:** on the logic a wrong answer would hide in. That means tier rules, column selection and unit conversion, the arithmetic checks, event clustering, signals, the verdict matrix, the citation guard, the rate limiter and the API's refusal paths.
- **Fakes vs real:** model calls are faked in tests. Real fixtures (NSE JSON, screener pages, results PDFs, a transcript) pin the parsers.

## Deliberately left out

- **Balance-sheet deep-dive, working-capital cycle, narrative-vs-numbers on the annual report:** Promised vs Delivered covers the brief's favourite analysis more rigorously.
- **LinkedIn bios:** the appointment filing is a primary source and always available. Scraping LinkedIn is brittle and against its terms.
- **Web push notifications:** alerts update on each scheduled refresh; push would need a service worker and subscription storage.
- **Intraday or real-time feeds:** the brief's data is end-of-day.
- **Acting on items, editing the portfolio, comparison views:** I considered these for interactivity and built only Chat, which reaches furthest with one new surface.

## Next

1. **Swipe to triage Brief cards,** with dismissals that teach the tier rules.
2. **Web push** for critical alerts.
3. **A real-time exchange feed** instead of 2-hourly polling.
4. **Accounts,** so each investor has their own portfolio.
5. **Grading regulatory fines by size** against revenue.

## Run it locally

```bash
cp .env.example .env            # NVIDIA_API_KEY=… (free at build.nvidia.com)
cd backend && uv sync && uv run pytest -q
uv run python -m finn.ingest --days 7          # writes data/snapshot/
uv run python -m finn.pull.dossier --symbols PIDILITIND
cd ../web && npm install && npm run dev        # http://localhost:5173
make eval                                      # accuracy tables
make api                                       # live research server on :8000
```

## How it was built

- **Builder:** Claude Code (Opus), working from a written plan that was reviewed and revised before any code.
- **The plan:** [docs/superpowers/plans/2026-10-28-finn.md](docs/superpowers/plans/2026-10-28-finn.md)
- **Data-source spikes and the decisions they forced:** [docs/spikes.md](docs/spikes.md)
- **Task-by-task progress log:** [docs/PROGRESS.md](docs/PROGRESS.md)
- **Every request, with its outcome (wording edited for clarity):** [docs/PROMPTS.md](docs/PROMPTS.md)
- **Build history:** [FINN_BUILD_HISTORY_EXPORT/](FINN_BUILD_HISTORY_EXPORT/FINN_AI_BUILD_HISTORY.md), a written account of the build with the exact, unedited session transcripts in [source_sessions/](FINN_BUILD_HISTORY_EXPORT/source_sessions/), both readable Markdown and raw `.jsonl` (only secrets and my email are redacted)
