# FINN — AI-Assisted Build History

**Build period:** 28 October–1 November 2026  
**Project:** FINN — an AI-assisted equity research and portfolio-monitoring application for Indian listed companies  
**Build record:** 65 curated substantive requests, supported by two preserved Claude Code session exports

## 1. Project objective

FINN was built as an end-to-end research product for an investment challenge. Its aim is to turn company announcements, quarterly results, financial statements, transcripts, annual reports and market prices into a concise, source-linked view of what matters to an investor.

The product combines two workflows:

- **Push:** surface material company events and unusual price or volume activity without flooding the investor with routine filings.
- **Pull:** let a user request a researched company dossier, inspect financial performance and management guidance, and ask questions grounded in that saved research.

The central product decision was to prioritise a dependable, evidence-linked workflow over a broad interface that could not be demonstrated reliably. The implementation was delivered in short vertical slices, beginning with real-source validation and a deployed one-company path before expanding to the full portfolio and research features.

## 2. Build approach and engineering principles

The initial implementation plan was revised before coding to prioritise data-source spikes, a minimal shared foundation, and a deployed end-to-end slice. The main engineering principles carried through the build were:

1. **Validate sources before depending on them.** Real exchange responses, company pages and results PDFs were tested and saved as fixtures. Source-specific failures and fallbacks were recorded.
2. **Use deterministic code for facts and calculations.** Rules classify filings before an LLM is called. Financial ratios, quarter selection, arithmetic checks, price signals and Promised-vs-Delivered verdicts are computed in code.
3. **Use models for extraction and language, not unchecked decisions.** Models read difficult document pages, extract structured guidance and write concise explanations. They do not invent financial values or decide whether a target was met.
4. **Keep every research claim traceable.** Dossier statements are linked to source material. The Chat workflow retrieves from the saved research corpus and uses a relevance/citation guard rather than answering from general model knowledge.
5. **Make the demo resilient.** Saved snapshots and precomputed dossiers support instant views. Stale, empty, unreadable and unavailable-source states are explicit instead of failing silently.
6. **Control model usage.** A shared gateway handles routing, throttling, caching and request limits. Cached research can be served without triggering a new model run.

## 3. Data-source validation

The first implementation milestone was a set of throwaway data spikes. Their findings shaped the later ingestion and extraction design.

| Source | Observed result | Design decision |
|---|---|---|
| NSE announcements | Worked for INFY, HDFCBANK and RELIANCE after first visiting the NSE homepage to establish cookies. | Use NSE as the primary announcements feed; do not rely on plain unauthenticated `curl` calls. |
| BSE announcements API | Scripted requests returned HTTP 403 / Access Denied. | Do not use this API as the announcements fallback. |
| NSE results-PDF archive | Downloads were inconsistent: INFY was retrieved, while an HDFCBANK PDF was truncated. | Validate every downloaded PDF; do not assume a successful HTTP response means a complete document. |
| BSE file server | A complete HDFCBANK results PDF and a Pidilite transcript were retrieved through document links. | Use the file server as a document-download fallback where appropriate. |
| screener.in | Company pages and quarterly tables loaded without a login in the tested requests. INFY quarterly values matched its filing. | Use its standardised quarterly tables for numeric financial data and its links to company documents. |
| yfinance | Price data was retrieved for tested symbols. The current intraday bar could be incomplete during market hours. | Exclude the current trading day's unfinished bar from signal calculations. |

The PDF spike exposed an important quality issue: text extraction alone was not dependable for scanned results statements. The implementation therefore used a vision model to read the relevant statement-page image, then validated the extracted figures against arithmetic and the standardised quarterly table. Hand-checked figures and real responses were kept as fixtures.

The detailed source observations and fixture-level results belong in `docs/spikes.md` in the project repository. The table above is a concise summary of the recorded spike outcomes, not a claim that every endpoint is universally available from every network.

## 4. Product and architecture evolution

### 4.1 Foundation and deployment

The foundation introduced shared data models, a snapshot store, a portfolio configuration and a single model gateway. The gateway routes work by task, applies throttling and caching, and enforces request controls.

The first deployment used a Hugging Face Space for the web application and a Render service for the API and live research. GitHub became the source repository and the scheduled-ingestion runner. The deployed application serves saved snapshots and dossiers for the instant path; live research is used when a requested company does not already have a saved report.

### 4.2 Push: filings, results and alerts

The first complete stock slice used INFY. An ingestion command fetched its filings, classified them, enriched the relevant events and wrote a snapshot that appeared in the deployed Brief screen.

The Push experience was then expanded across the 18-stock portfolio:

- Announcements are classified as **critical**, **notable** or **routine**. Deterministic rules handle the large majority before the model is called; the build log records approximately 92% rule-based classification.
- Related same-day filings are clustered into a single event so that a results announcement, board outcome, presentation and related disclosure do not overwhelm the feed as separate items.
- Results cards extract quarterly financial values, choose the correct quarter columns, convert units, check arithmetic and re-read difficult values at higher resolution when needed.
- Banks and NBFCs use a lender-specific presentation based on NII and PPOP where available, rather than treating EBITDA as a meaningful lender metric.
- Management-change cards use information contained in the filing. When the filing has no profile, the product says so and links the source rather than scraping LinkedIn.
- Watch adds user-defined price and volume thresholds, historical 30-day trigger counts and an alert inbox.
- Scheduled ingestion refreshes the portfolio on market days and in the evening. The workflow was later adjusted to avoid top-of-hour scheduling conflicts and given a watchdog for overdue runs.

### 4.3 Pull: company research dossiers

The research workflow builds a structured dossier from the company's financial history and published material. Its main sections include a financial snapshot, Promised vs Delivered, a business snapshot and bull-versus-bear analysis.

Financial metrics such as growth, margins, returns, leverage and cash conversion are computed deterministically from the standardised quarterly data. For guidance analysis, the model extracts structured targets (including the metric, comparison, value, period and supporting quote); code selects the corresponding actual and computes the verdict. The model is limited to the explanatory sentence and cannot override the computed verdict.

The dossier uses citations so a reader can trace research claims to the underlying filing, transcript or annual report. A guard removes unsupported claims. Existing dossiers are saved and reused; a daily rebuild checks the portfolio holdings for new results, calls or annual reports. The earlier idea of prebuilding the entire Nifty 50 was stopped after the freshness trade-off was reviewed. Companies outside the holdings and demo set are researched when requested, and their completed dossiers are saved for future use.

### 4.4 Ask, Chat and portfolio interaction

The original three-tab shell was extended as the product evolved. The completed README records a five-tab interface, including a Portfolio view and a Chat experience.

Portfolio presents a compact view of holdings and their movement over 1-week, 1-month and 3-month windows, with the biggest movers surfaced first. Research generation gained a progress indicator based on server-reported completed steps, a queue for concurrent work, shared builds for duplicate requests, and in-app/system notifications when work is ready.

Chat was deliberately constrained to the saved research corpus. It uses an index of cited report passages, hybrid retrieval and a relevance gate. It answers about holdings and companies that have already been researched; for other companies, it returns a research-pending response rather than manufacturing an answer. The intended interaction is natural-language questions grounded in dossier evidence, not an unrestricted financial chatbot.

### 4.5 Reliability and final architecture documentation

A user-reported issue showed that live research could fail after the browser tab was left. Two separate failure modes were investigated:

- The browser could lose the streaming connection even though the server-side build was still running. The client was changed to rejoin the existing build rather than abandon it.
- Render's free service could stop after a period without incoming requests. A conditional keep-awake request was added while a build is in progress.

A Gemini fallback was also added around the existing model gateway. NVIDIA remains the primary provider; when its request fails after retries, the same request can be routed to `gemini-3.5-flash`, subject to the available free-tier quota.

The README was updated with an architecture image and four Mermaid flowcharts covering the system overview, scheduled ingestion, live research for a new company, and Chat. The final export notes that the diagrams should still be checked in GitHub's renderer and on a phone before public submission.

## 5. Model strategy and measured checks

The model stack was selected by testing the available API options against the project's actual jobs rather than choosing models by name alone. The final recorded routing was:

| Job | Recorded model | Role |
|---|---|---|
| Scanned results-page reading | `nvidia/nemotron-3.5-super-vl-120b-a12b` | Primary vision extraction for statement-page images. |
| Bulk text extraction and classification | `nvidia/nemotron-3.5-lightning-30b-a3b` | One-line summaries, structured extraction and other high-volume text work. |
| Reasoning sections | `nvidia/nemotron-3-ultra-550b-a55b` | Higher-level reasoning such as bull-versus-bear analysis. |
| Emergency fallback | `gemini-3.5-flash` | Fallback when NVIDIA fails after its retry policy; limited by the free-tier quota. |

The build log records the following evaluation results. They refer to different checks and should not be conflated:

| Check | Recorded result | Qualification |
|---|---:|---|
| Early NVIDIA vision spike | 97% (64/66 fields over three runs) | The remaining error was a HDFCBANK PBT digit misread; arithmetic validation was used to catch it. |
| Final results-extraction evaluation | 57/57 fields | Reported as the completed Task 14 accuracy check. |
| Guidance extraction | 3/3 expected items recalled | Reported in the Task 14 completion summary. |
| Gemini results-extraction check | 57/57 fields | Tested with NVIDIA disabled; this used the free-tier quota. |
| Gemini guidance evaluation | Not measured | The free-tier daily quota was exhausted before this part of the check completed. |
| Announcement rule coverage | Approximately 92% | Share of classifications handled by deterministic rules, as reported in the build log. |

The final test run recorded **260 backend tests and 40 web tests passing**. These are the counts reported at the end of the captured build session; they are not a guarantee that a later code revision has the same result.

## 6. What changed through iteration

Several decisions were deliberately revised as the product was tested:

- The original plan favoured a narrow three-tab workflow; Portfolio and Chat were added only after the core Push and Pull workflows existed.
- A broad Nifty 50 prebuild was explored, but removed when freshness was judged more valuable than instant availability for every company. Holdings and demo dossiers remain saved; other companies are researched on demand.
- A faster extraction strategy based on passage-level processing was tried and reverted when it failed the accuracy gate. Parallel reading was retained where it helped without lowering extraction quality.
- A third-party scheduling service was considered, then rejected in favour of GitHub scheduling plus a watchdog to keep the ingestion workflow within the existing deployment setup.
- Gemini was added as a fallback, not as a second model sharing every request. Its quota is too small for a full analysis, but it can rescue individual failed calls.

These changes reflect a consistent preference for source freshness, measured accuracy and a working demo over speculative speed or broad precomputation.

## 7. Known limitations at the end of the captured build

The final session did not establish that every long-running build would reliably finish with no browser connected:

- An off-screen Maruti analysis did not save after the client disconnected. A later Maruti run with a viewer attached completed in 136 seconds, but reused cached work, so it was not a clean cold-run comparison.
- TVS Motor, a company without a prior saved report, completed and saved in 13 minutes with no viewer attached. However, that run finished inside Render's 15-minute idle window, so it did **not** conclusively test whether the keep-awake mechanism would sustain a longer build.
- Gemini's free tier was recorded as 20 requests per day. A full new analysis can require substantially more calls, so Gemini is a limited emergency fallback, not a dependable provider for an entire build. Its guidance accuracy remained unmeasured.
- Some source endpoints behaved differently depending on cookies or the server/network used. The spike results are evidence for the tested environment and dates, not a universal availability guarantee.

## 8. AI-assisted development record

The work was carried out through Claude Code sessions using the Superpowers, Context7 and frontend-design plugins. The prompt log records 65 substantive requests grouped by planning, data validation, Push, Pull, product iteration, interface/scheduling and reliability/final checks.

The prompt log is a readable, curated account of those requests and their outcomes. The exact wording is in the two original session exports, in both Markdown and JSONL formats, preserved unchanged in this package.

- [Curated prompt log](PROMPTS.md)
- [Session 1 — Markdown transcript](source_sessions/5cc6a662-768e-4653-b659-84ab7b01e825.md) · [JSONL archive](source_sessions/5cc6a662-768e-4653-b659-84ab7b01e825.jsonl)
- [Session 2 — Markdown transcript](source_sessions/df29b36f-b1bf-4d4e-862b-29df1f45cd68.md) · [JSONL archive](source_sessions/df29b36f-b1bf-4d4e-862b-29df1f45cd68.jsonl)
