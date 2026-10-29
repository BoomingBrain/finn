# Interactive FINN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the investor act, not just read:
- triage Brief items
- ask FINN a question in their own words
- choose which companies are in their portfolio
- compare companies side by side

**Architecture:**
- **Triage, portfolio choice and comparison are browser-only:** state lives in `localStorage` per device, and everything is computed from the static snapshot files, so they're instant and cost nothing.
- **Free-text questions are the one new server call:** `POST /api/ask/{symbol}` on Render answers from that company's dossier only, through the fast model with the existing citation guard, so every sentence is grounded and cited.
- **A wider covered universe:** to let the investor add companies, ingestion widens from the 18 holdings to a covered universe (holdings plus the Nifty 50 list), so filings and prices exist for anything they can add.

**Tech Stack:** React 18 + TypeScript + Tailwind v4 + Vitest (web); Python 3.12 + FastAPI + pytest (backend).

**Spec:** the user's choice on 29 Oct of four ideas from the brainstorm: "acting on an item, such as dismissing, saving or following up; asking FINN a question in your own words; changing what's in the portfolio; comparing companies". The user opted out of further questions, so the design calls below are the plan author's and are marked **Call:** for review.

## Global Constraints

- **Viewers cost nothing** except when they ask a question. Triage, portfolio and compare make no server or model calls.
- **No claim without a page:** every sentence of an answer must cite a source id from the dossier, through `sections.drop_uncited`. An answer with nothing grounded says so.
- **No new dependencies** (web or backend).
- **Existing visual rules:** numbers in `StatBox`; colour only for direction and tier; text in hairline rows; serif only for company names and the one statement per screen.
- **No accounts.** **Call:** per-device `localStorage` (via `useStoredState`), since the prototype has no sign-in. The README says so.
- **Rate limits:** questions get their own limiter, 30 per IP an hour (`ASK_PER_IP_PER_HOUR`), plus the existing daily request budget.
- **No backend push while the queued Kotak live-timing test (faster-research plan, Task 4) is running:** a Render redeploy kills in-flight builds. Commit locally and push after it reports.

## Review Focus

1. **A question the dossier can't answer** ("What's the CEO's salary?") gets "The research on {name} doesn't cover that." Never an uncited answer. *Test in Task 2:* `test_unanswerable_question_says_not_covered`.
2. **A question about a company with no dossier** gets a prompt to research it first, not a server error. *Test in Task 2:* `test_question_without_dossier_is_404`.
3. **The investor removes every holding.** Brief, Portfolio and Watch show "No companies in your portfolio" with a link to add some, not a crash or a blank page. *Test in Task 5:* `test_empty_portfolio_shows_add_prompt`.
4. **A dismissed or saved id that no longer exists** (the event aged out of the 60-day window) is ignored, not shown as a broken card. *Test in Task 1:* `test_stale_ids_are_ignored`.
5. **Comparing a company whose snapshot is unavailable** shows "—" in its column, not a crash. *Test in Task 6:* `test_missing_values_show_dash`.

---

## File Structure

- `web/src/lib/triage.ts` (+ test): triage state and filtering. `web/src/components/CardActions.tsx`. Modify `EventCard.tsx` and `screens/Brief.tsx`.
- `backend/finn/pull/qa.py` (+ `tests/test_qa.py`): answer a question from a dossier. Modify `backend/finn/api.py` and `tests/test_guard.py`.
- `web/src/components/QuestionBox.tsx` (+ test). Modify `screens/Ask.tsx`.
- `backend/finn/portfolio.py`, `backend/finn/ingest.py`: covered universe; `universe.json`. Tests in `tests/test_ingest.py`.
- `web/src/hooks/useHoldings.ts`, `web/src/lib/holdings.ts` (+ test), `web/src/components/PortfolioEditor.tsx`. Modify `screens/Portfolio.tsx`, `Brief.tsx`, `Watch.tsx`, `hooks/useAlerts.ts`.
- `web/src/screens/Compare.tsx`, `web/src/lib/compare.ts` (+ test). Modify `hooks/useHashRoute.ts`, `App.tsx`, `screens/Ask.tsx`.

---

### Task 1: Triage Brief items (save, dismiss, note)

**Files:** Create `web/src/lib/triage.ts`, `web/src/lib/triage.test.ts`, `web/src/components/CardActions.tsx`. Modify `web/src/components/EventCard.tsx`, `web/src/screens/Brief.tsx`.

**Interfaces:**
- Produces: `type Triage = { saved: Record<string, { at: string; note: string }>; dismissed: string[] }`.
  - `toggleSaved(t, id, now: string): Triage`, `setNote(t, id, note): Triage`, `dismiss(t, id): Triage`, `undismiss(t, id): Triage`.
  - `applyTriage(events: Event[], t: Triage, view: "inbox" | "saved"): { shown: Event[]; dismissedCount: number }`.
  - Hook `useTriage(): [Triage, (t: Triage) => void]`, using `useStoredState("finn.triage", { saved: {}, dismissed: [] })`.
- **Call:** "follow up" = save with an optional one-line note ("check margin next quarter"). It shows on the card and in the Saved view.
- **UI:**
  - Each EventCard footer gets **Save** (filled marker when saved), **Dismiss**, then the existing Open filing and Ask about this.
  - The Brief shows a two-option switch, **Inbox / Saved (n)**, beside the window chips.
  - Inbox hides dismissed events and ends with "{n} dismissed — Show"; showing them gives each an **Undo**.
  - Saved lists saved events regardless of the time window, each with its note field.

- [ ] **Step 1: Write the failing tests** (`triage.test.ts`):
  - `test hides dismissed in inbox and counts them`: 3 events, 1 dismissed → `shown.length === 2`, `dismissedCount === 1`.
  - `test saved view ignores the window and keeps notes`: `toggleSaved` then `setNote(…,"check margin")` → the saved view contains the event, and `t.saved[id].note === "check margin"`.
  - `test toggleSaved twice unsaves`.
  - `test_stale_ids_are_ignored`: dismissed and saved ids not in `events` → `dismissedCount === 0`, and the saved view is empty.
- [ ] **Step 2:** Run `cd web && npx vitest run src/lib/triage.test.ts`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement `triage.ts`, `CardActions.tsx`, and the EventCard and Brief changes.
- [ ] **Step 4:** Run `npx tsc -b && npx vitest run`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: save, dismiss and note Brief items`.

### Task 2: Answer a question from a dossier (backend)

**Files:** Create `backend/finn/pull/qa.py`, `backend/tests/test_qa.py`. Modify `backend/finn/api.py`, `backend/tests/test_guard.py`.

**Interfaces:**
- Consumes: `sections.GROUNDING_RULES`, `sections.drop_uncited`, `sections.Point`, `LLM.complete_json("bulk", …)`, the dossier dict shape (`sections[].section/status/data/citations`).
- Produces:
  - `dossier_sources(dossier: dict) -> dict[str, str]`: source id → text. Content:
    - `SCR`: the snapshot rendered with `sections.snapshot_text` from the snapshot data.
    - each delivery row's `source_id`: "Management said: "{quote}" | delivered … | verdict: …" in plain verdict words, via `sections.VERDICT_WORDS`.
    - each business `source_id`: what it does, plus segments with shares.
    - each bull/bear point's ids: "Bull: …" / "Bear: …".
  - `Answer(points: list[Point])`.
  - `answer_question(dossier: dict, question: str, llm: LLM) -> list[Point]`:
    - bulk tier, prompt = `GROUNDING_RULES` + "Answer in at most 4 short sentences …" + the sources
    - `drop_uncited` against `dossier_sources` keys
    - at most 4 points
  - `NOT_COVERED = "The research on {name} doesn't cover that."`
  - **API:** `POST /api/ask/{symbol}` with JSON `{"question": str}` (1–300 chars after strip, else 400 `{"error":"bad_question"}`). Order:
    1. dossier lookup: local store, else live memory, else `saved.load`; none → 404 `{"error":"no_dossier"}`
    2. ask limiter, 30 per IP an hour, else 429 `{"error":"rate_limited"}`
    3. `budget.check()`, else 429 `{"error":"budget_exhausted"}`
    4. answer → 200 `{"points":[{text,source_ids}], "citations":[Citation…], "not_covered": bool}`. `citations` is the dossier's own citations filtered to the cited ids. When `points` is empty, `not_covered: true` and one point `{text: NOT_COVERED, source_ids: []}`.
  - CORS: add `"POST"` to `allow_methods`.

- [ ] **Step 1: Write the failing tests**:
  - `test_answer_keeps_only_cited_points` (fake LLM returns one cited and one uncited point → one kept).
  - `test_unanswerable_question_says_not_covered` (fake returns `{"points":[]}` → API `not_covered: true` and the fixed text).
  - `test_question_without_dossier_is_404`.
  - `test_ask_is_rate_limited_separately` (`ASK` limiter at 1 an hour: the second call → 429; research is unaffected).
  - `test_bad_question_400` (empty, and 301 chars).
  - `test_sources_use_plain_verdict_words` (a `not_checkable` row → its text contains "cannot be checked", not "not_checkable").
- [ ] **Step 2:** Run `cd backend && uv run pytest tests/test_qa.py tests/test_guard.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `qa.py` and the endpoint. `create_app(..., ask_limiter: RateLimiter | None = None)`, defaulting to `ASK_PER_IP_PER_HOUR` = 30.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: ask a question answered only from the dossier`.

### Task 3: Question box on the dossier (web)

**Files:** Create `web/src/components/QuestionBox.tsx`, `web/src/components/QuestionBox.test.tsx`. Modify `web/src/screens/Ask.tsx`, `web/src/api/types.ts`.

**Interfaces:**
- Consumes: Task 2's endpoint and response; `apiBase`; `CitationChip`.
- Produces:
  - `askQuestion(symbol: string, question: string): Promise<QaResult>`, where `QaResult = { points, citations, not_covered } | { error: string }`.
  - `QuestionBox({ symbol, name })`:
    - Shown under the dossier once it is `done` and has no error.
    - **Input:** a text field with placeholder "Ask about {name}, e.g. is debt a concern?" and an **Ask** button (disabled while waiting or empty).
    - **Suggestion chips:** "Did they deliver on guidance?", "Is debt a concern?", "What's the biggest risk?"
    - **History:** the conversation is kept in component state, newest first. Each item shows the question, then the answer points with citation chips.
    - **Fixed error copy:**
      - `no_dossier`: "Research {name} first; questions are answered from its report."
      - `rate_limited`: "You've asked 30 questions this hour. Try again later."
      - `budget_exhausted`: "Today's AI budget is used up."
      - network: "Couldn't reach the research server."
    - **Waiting state:** "Reading the report…".

- [ ] **Step 1: Write the failing tests** (mock `fetch`):
  - `test shows cited answer points with chips`.
  - `test shows not-covered message`.
  - `test maps rate_limited to fixed copy`.
  - `test suggestion chip fills and submits`.
- [ ] **Step 2:** Run `npx vitest run src/components/QuestionBox.test.tsx`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npx tsc -b && npx vitest run`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: question box on research reports`.

### Task 4: Covered universe for filings and prices (backend)

**Files:** Modify `backend/finn/portfolio.py`, `backend/finn/ingest.py`, `backend/finn/snapshot.py`. Test `backend/tests/test_ingest.py`.

**Interfaces:**
- Produces:
  - `Portfolio.universe() -> list[Holding]`: the holdings, then every symbol in `finn/data/nifty50.txt` not already held. Names come from `guard.nse_symbols()`, `sector=None`.
  - `ingest(..., universe: bool = True)` fetches announcements and prices for the universe. The `--symbols` CLI still narrows it.
  - `signals.json` `names` covers the universe.
  - New `universe.json` = `{"holdings": [symbols…], "universe": [{"symbol","name"}…]}`, via `SnapshotStore.save_universe(dict)`.
- **Call:** one list covers both what can be added and what is ingested, so anything the investor adds already has filings and prices. **Cost:** more filings to classify and enrich, mostly rules; results cards use the vision model in results season.

- [ ] **Step 1: Write the failing tests**:
  - `test_universe_is_holdings_then_nifty_without_duplicates`.
  - `test_ingest_covers_the_universe` (fake fetch records the symbols asked for: holdings ⊂ asked, and a Nifty name ∈ asked).
  - `test_universe_json_marks_holdings`.
- [ ] **Step 2:** Run `uv run pytest tests/test_ingest.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass. Then run `uv run python -m finn.ingest --days 2` once. Expected: `universe.json` is written and `signals.json` has ≥ 50 names.
- [ ] **Step 5: Commit** `feat: covered universe for filings and prices`.

### Task 5: Choose your portfolio (web)

**Files:** Create `web/src/lib/holdings.ts`, `web/src/lib/holdings.test.ts`, `web/src/hooks/useHoldings.ts`, `web/src/components/PortfolioEditor.tsx`. Modify `web/src/screens/Portfolio.tsx`, `Brief.tsx`, `Watch.tsx`, `web/src/hooks/useAlerts.ts`, `web/src/App.tsx`.

**Interfaces:**
- Consumes: `universe.json` (Task 4).
- Produces:
  - `useHoldings(): { holdings: Set<string>; universe: {symbol,name}[]; toggle(symbol): void; reset(): void; ready: boolean }`. Stored as `finn.holdings` (a symbol list), defaulting to `universe.json` `holdings` when unset. Lifted into `App`, like settings, so every tab agrees.
  - `filterEvents(events, holdings)`, `filterSeries(signals, holdings)` in `holdings.ts`.
  - Brief, Portfolio, Watch and alerts use only held symbols. The Portfolio headline says "your {n} holdings".
- **UI:** an **Edit portfolio** button on the Portfolio tab opens `PortfolioEditor` in place. It has:
  - a search box
  - one hairline row per company: name, ticker, and a toggle **Add / Remove** (aria-pressed)
  - current holdings first, then a count line "{n} of {universe} companies"
  - **Reset to the original 18**
  - **Done**
- **Empty state, all tabs:** statement "No companies in your portfolio." with an **Add companies** link that opens the editor.

- [ ] **Step 1: Write the failing tests**:
  - `filterEvents keeps only held symbols`.
  - `filterSeries keeps only held symbols`.
  - `test_empty_portfolio_shows_add_prompt` (render Portfolio with an empty holdings set → the text and the link).
  - `editor toggles a company` (click Add → in the set; click Remove → out).
- [ ] **Step 2:** Run `npx vitest run src/lib/holdings.test.ts`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npx tsc -b && npx vitest run`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: choose the companies in your portfolio`.

### Task 6: Compare companies (web)

**Files:** Create `web/src/lib/compare.ts`, `web/src/lib/compare.test.ts`, `web/src/screens/Compare.tsx`. Modify `web/src/hooks/useHashRoute.ts` (tab `"compare"` is reachable by route but not shown in the TabBar), `web/src/App.tsx`, `web/src/screens/Ask.tsx`.

**Interfaces:**
- Consumes: static dossiers via `useResearch`, `StatBox`, `toneAbove` / `toneBelow` / `directionClass`.
- Produces:
  - `COMPARE_ROWS`: label, value getter, formatter and tone, for:
    - revenue (last 4 quarters) and its 3-year growth
    - profit (last 4 quarters) and its 3-year growth
    - operating margin, ROCE (or ROE for lenders), debt to equity, cash ÷ profit
    - promises met / missed (from delivery counts)
    - red flags (count)
  - `compareValue(row, snapshot | undefined) -> { text: string; tone: string }`: "—" with a muted tone when missing.
  - Route `#/compare/A,B` (2–3 symbols).
- **Layout:**
  - one sticky header row of company names (serif) and a column per company; rows in hairline style
  - per row, the best value gets a small marker: the highest for higher-is-better rows, the lowest for debt
  - a **Compare with…** link at the bottom of every dossier opens a picker of ready companies (from `symbols.json` `precomputed`), then the route
  - the Ask home gets a "Compare companies" link to the picker
- **Call:** up to 3 columns to fit a 360 px screen; ready dossiers only, since comparing is meant to be instant.

- [ ] **Step 1: Write the failing tests**:
  - `test_missing_values_show_dash`.
  - `best value marked: higher margin wins, lower debt wins`.
  - `parses #/compare/INFY,TCS into two symbols and drops a fourth`.
- [ ] **Step 2:** Run `npx vitest run src/lib/compare.test.ts`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npx tsc -b && npx vitest run`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: compare companies side by side`.

### Task 7: Ship and check on a phone width

**Files:** Modify `README.md` (feature list, per-device note, ask endpoint), `docs/PROGRESS.md`, `docs/PROMPTS.md`.

- [ ] **Step 1:** Run the backend and web suites. Expected: all pass.
- [ ] **Step 2:** Screenshot at 390 px:
  - Brief with Saved selected
  - a dossier with a question answered (live Render)
  - the portfolio editor
  - a compare of two companies

  Fix anything that clips or overflows.
- [ ] **Step 3:** Push (no live research test running), `make deploy-space`. Then `curl -X POST $RENDER_URL/api/ask/PIDILITIND -d '{"question":"Did they meet margin guidance?"}' -H 'Content-Type: application/json'`. Expected: 200 with cited points.
- [ ] **Step 4: Commit** `docs: interactive features`.
