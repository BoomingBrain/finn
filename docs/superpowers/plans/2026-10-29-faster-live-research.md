# Faster Live Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut a live dossier build for a new NSE ticker from 15–30 min to under 8 min, and make the most likely tickers instant, without losing guidance accuracy.

**Architecture:**
- **Where the time goes:** guidance extraction sends every transcript page to the 550B reasoning model in 16k-char chunks, about 20 calls of 1–3 min at 2 in flight. That is ~85% of a live build (measured on KOTAKBANK, 28 Oct: 3 calls read in 7 min).
- **Fix 1:** send only the pages that can hold a numeric target.
- **Fix 2:** read the annual report while the calls are being read.
- **Fix 3:** prebuild the Nifty 50 a few at a time each night, so most tickers a reviewer types are static and instant.
- **Deliberately left out:**
  - **More reasoning calls in flight:** HTTP 429 at 4 on 28 Oct.
  - **Thinking off or a smaller extraction model:** GPT-OSS-20B and the bulk model both missed real targets on the gold set.

**Tech Stack:** Python 3.12, asyncio, pytest (backend); GitHub Actions; existing `make eval` gold set.

**Spec:** the speed analysis in `docs/PROGRESS.md` (2026-10-28 entries "Queued live research…" and "Multi-model extraction pool…") and the user's request "how to make it faster live research".

## Global Constraints

- **Accuracy gate:** guidance recall on `make eval` must stay **3/3** and precision **100%**. If a change drops either, it doesn't ship.
- **Reasoning-tier concurrency stays 2** (`llm.CONCURRENCY["reason"]`). 4 in flight triggered HTTP 429 on 28 Oct.
- **Model pool stays `[nemotron-3-ultra-550b-a55b]`** (`llm.POOLS["extract"]`). No other model on this key passed `make eval`.
- **Daily refresh scope is unchanged:** `.github/workflows/dossiers.yml` checks only the 18 holdings (`--holdings`). Prebuilt tickers are never refreshed (user decision, 28 Oct).
- **Section order unchanged:** snapshot, delivery, business, bull_bear. Fixed reasons and SSE shape unchanged.
- **No backend push while a live Render test is running.** A Render redeploy kills in-flight builds.

## Review Focus

1. **Guidance in a table or slide-style page:** numbers with no forward-looking word on the same page (e.g. a "Guidance" heading, figures below) must still be sent. *Test in Task 1:* `test_candidate_pages_keep_guidance_headings`.
2. **A quote running across a page break** must still validate. The page after each candidate is sent too. *Test in Task 1:* `test_candidate_pages_include_the_next_page`.
3. **A transcript with no candidate pages** returns `[]` with zero model calls, and the delivery section is still `ready`, not failed. *Test in Task 1:* `test_no_candidates_means_no_call`.
4. **The annual-report fetch failing while calls are being read:** the business section is `unavailable`, and delivery is untouched. *Test in Task 2:* `test_business_failure_does_not_touch_delivery`.
5. **The nightly prebuild must not eat the day's budget or run long:** at most `--limit` builds per run, and only symbols without a dossier. *Test in Task 3:* `test_limit_caps_new_builds`.

---

## File Structure

- `backend/finn/pull/guidance.py`: add `candidate_pages()`; `extract_targets()` sends only candidates.
- `backend/finn/pull/dossier.py`: run `_business` concurrently with `_delivery`; add `--symbols-file` and `--limit` to the CLI.
- `backend/finn/data/nifty50.txt`: one NSE symbol per line.
- `.github/workflows/prebuild.yml`: nightly prebuild of missing Nifty 50 dossiers.
- Tests: `backend/tests/test_guidance.py`, `backend/tests/test_sections.py`.
- Docs: `README.md` (live-build time), `docs/PROGRESS.md`, `docs/PROMPTS.md`.

---

### Task 1: Send only candidate pages to guidance extraction

**Files:**
- Modify: `backend/finn/pull/guidance.py` (`extract_targets`, new `candidate_pages`)
- Test: `backend/tests/test_guidance.py`

**Interfaces:**
- Consumes: `DocText(pages)`, `LLM.complete_json(..., pool="extract")`.
- Produces: `candidate_pages(doc: DocText) -> list[int]`, 1-based, sorted, de-duplicated. `extract_targets()` keeps its signature. Page ids stay the original page numbers (`T:{date}:p{n}`), so citations still open the right page.

**Selection rule:** a page is a candidate if either holds:
- it has a number with a unit (`%`, `percent`, `crore`, `cr`, `bps`, `basis points`, `x`, `times`, `lakh`, `billion`) **and** a forward word (`expect`, `guid`, `target`, `aim`, `outlook`, `going forward`, `next year`, `this year`, `FY ?2\d`, `for the year`, `aspire`, `plan to`, `looking at`, `should be`, `will be`)
- it contains `guidance` or `outlook` alone

The page after every candidate is added too.

- [ ] **Step 1: Write the failing tests**

```python
def test_candidate_pages_pick_numeric_forward_statements():
    doc = DocText(url="u", pages=["Welcome everyone.", "We expect revenue growth of 12% in FY27.", "Thank you.", "Q&A small talk."])
    assert candidate_pages(doc) == [2, 3]  # page 2, plus the next page

def test_candidate_pages_keep_guidance_headings():
    doc = DocText(url="u", pages=["Intro", "Guidance", "Margin 20-24%", "Bye"])
    assert 2 in candidate_pages(doc) and 3 in candidate_pages(doc)

def test_candidate_pages_include_the_next_page():
    doc = DocText(url="u", pages=["We will be at 20% to", "24% margin for the year."])
    assert candidate_pages(doc) == [1, 2]

def test_no_candidates_means_no_call(tmp_path):
    llm, fake = make_llm(tmp_path, [])
    assert extract_targets(DocText(url="u", pages=["Hello", "Thanks"] * 10), date(2026, 8, 1), llm) == []
    assert fake.calls == []

def test_only_candidate_pages_are_sent(tmp_path):
    pages = ["Opening remarks."] * 5 + ["We expect EBITDA margin of 20% to 24% for FY27."] + ["Q&A."] * 5
    llm, fake = make_llm(tmp_path, [json.dumps({"targets": []})])
    extract_targets(DocText(url="u", pages=pages), date(2026, 8, 1), llm)
    assert len(fake.calls) == 1
    assert "[T:2026-08-01:p6]" in fake.calls[0].user and "[T:2026-08-01:p1]" not in fake.calls[0].user
```

- [ ] **Step 2:** Run `cd backend && uv run pytest tests/test_guidance.py -q`. Expected: FAIL (`candidate_pages` not defined).
- [ ] **Step 3:** Implement `candidate_pages(doc)` and use it in `extract_targets`. Build the `pages` dict from candidates only. Grounding (page id sent, quote on page) still checks against those pages. Return `[]` before chunking when there are none.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass (existing `test_extract_targets_*` tests use pages with forward numbers, so they stay valid).
- [ ] **Step 5: Accuracy gate.** Run `make eval`. Expected:
  - guidance recall **3/3** and precision **100%**
  - results unchanged at 57/57

  If recall drops, widen the forward-word list by the missed sentence's wording and re-run, once. If it still drops, revert this task.
- [ ] **Step 6: Measure.** For PIDILITIND Aug 2026, HAL May 2026 and CDSL Aug 2026, log the number of extraction chunks before and after. Expected: at least 3× fewer chunks. Record the numbers in `docs/PROGRESS.md`.
- [ ] **Step 7: Commit** `perf: send only candidate pages to guidance extraction`.

### Task 2: Read the annual report while the calls are being read

**Files:**
- Modify: `backend/finn/pull/dossier.py` (`build_dossier`)
- Test: `backend/tests/test_sections.py`

**Interfaces:**
- Consumes: `_delivery(c, llm, fetch_text, urls, progress)`, `_business(c, llm, fetch_text, urls)`.
- Produces: `build_dossier` unchanged in signature and yield order.
  - Start `_business` as an `asyncio.create_task` right after the snapshot is yielded.
  - Await delivery, then await the business task.
  - Each section keeps its own `try/except` and reasons.
  - `Progress`: the annual-report step does `update(advance=1)` when the business task finishes, not `done=after_delivery`. Bull/bear still sets `done=after_business` before it starts. The final `done=total` is unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_annual_report_is_read_while_calls_are_read(tmp_path):
    # fetch_text for the transcript blocks until the annual report has been fetched: sequential code times out
    ar_fetched = threading.Event()
    def fetch(url):
        if url == "ar":
            ar_fetched.set(); return AR_DOC
        assert ar_fetched.wait(5), "annual report was not fetched in parallel"
        return TRANSCRIPT_DOC
    sections = run(llm_with_replies(tmp_path), company([TRANSCRIPT], [REPORT]), fetch_fn=fetch)
    assert [s.section for s in sections] == ["snapshot", "delivery", "business", "bull_bear"]

def test_business_failure_does_not_touch_delivery(tmp_path):
    def fetch(url):
        if url == "ar": raise DocumentError("BSE down")
        return TRANSCRIPT_DOC
    sections = run(llm_with_replies(tmp_path), company([TRANSCRIPT], [REPORT]), fetch_fn=fetch)
    assert sections[1].status == "ready" and (sections[2].status, sections[2].reason) == ("unavailable", "Analysis failed")
```

Lift the fixtures out of `test_full_dossier_cites_real_pages` into module constants:
- `TRANSCRIPT` (DocLink url `"t1"`) and `REPORT` (DocLink url `"ar"`)
- `TRANSCRIPT_DOC` and `AR_DOC` (the two DocTexts)
- `llm_with_replies(tmp_path)` (an LLM over the four canned replies, in call order extract, explain, business, bull/bear)

Extend `run()` with a `fetch_fn` override. The fake LLM must answer by prompt content, not call order, because business and extraction now run concurrently: match the system prompt for business vs extraction.

- [ ] **Step 2:** Run `uv run pytest tests/test_sections.py -q`. Expected: the parallel test FAILS (wait times out).
- [ ] **Step 3:** Implement as described in Interfaces.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass, including the existing progress assertions (monotonic, ends at total).
- [ ] **Step 5: Commit** `perf: read the annual report in parallel with the earnings calls`.

### Task 3: Prebuild the Nifty 50 each night

**Files:**
- Create: `backend/finn/data/nifty50.txt`, `.github/workflows/prebuild.yml`
- Modify: `backend/finn/pull/dossier.py` (`main`, `_precompute`)
- Test: `backend/tests/test_sections.py`

**Interfaces:**
- Consumes: `_precompute(symbols, store, llm, mode, parallel)`.
- Produces:
  - CLI `--symbols-file PATH` (one symbol per line, `#` comments allowed) and `--limit N` (at most N builds this run; skipped symbols don't count).
  - `_precompute(..., limit: int | None = None)`.
  - The file holds the 50 current Nifty 50 symbols minus those already in `portfolio.yaml`. Take the list from NSE's index constituents CSV (`https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv`, column `Symbol`).
  - **Workflow `prebuild.yml`:**
    - cron `0 21 * * *` (02:30 IST, after the 20:00 refresh), plus `workflow_dispatch`
    - runs `uv run python -m finn.pull.dossier --symbols-file finn/data/nifty50.txt --mode missing --limit 8 --parallel 2`
    - then the same commit (pull `--rebase` first) and `make deploy-space` steps as `dossiers.yml`
    - `concurrency: group: prebuild`, `timeout-minutes: 240`

- [ ] **Step 1: Write the failing test**

Import the module (`from finn.pull import dossier`) so `collect_dossier` can be monkeypatched.

```python
def test_limit_caps_new_builds(tmp_path, monkeypatch):
    built = []
    async def fake_collect(symbol, llm, **kw):
        built.append(symbol); return Dossier(symbol=symbol, name=symbol, built_at=datetime.now(timezone.utc), basis="", sections=[])
    monkeypatch.setattr(dossier, "collect_dossier", fake_collect)
    store = SnapshotStore(tmp_path)
    store.save_dossier("A", {"symbol": "A", "sections": []})  # exists: skipped, not counted
    asyncio.run(dossier._precompute(["A", "B", "C", "D"], store, llm=None, mode="missing", parallel=1, limit=2))
    assert built == ["B", "C"]
```

- [ ] **Step 2:** Run `uv run pytest tests/test_sections.py::test_limit_caps_new_builds -q`. Expected: FAIL (unexpected `limit`).
- [ ] **Step 3:** Implement `limit`: decide which symbols need a build first, keep the first `limit` in input order, then build them. Add the CLI flags, `nifty50.txt` and `prebuild.yml`.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass. Then run `uv run python -m finn.pull.dossier --symbols-file finn/data/nifty50.txt --mode missing --limit 0`. Expected: exits with no builds.
- [ ] **Step 5: Commit** `feat: prebuild the Nifty 50 a few dossiers a night`. After pushing, start one run with `gh workflow run prebuild.yml -R BoomingBrain/finn` and confirm it commits ≤ 8 new dossiers and redeploys.

### Task 4: Verify on Render and update the stated times

**Files:**
- Modify: `web/src/components/BuildProgress.tsx`, `web/src/components/SymbolSearch.tsx` (time copy), `README.md`, `docs/PROGRESS.md`, `docs/PROMPTS.md`

**Interfaces:**
- Consumes: the deployed API from Tasks 1–2.
- Produces: measured live-build time on Render; copy that states it.

- [ ] **Step 1:** Push Tasks 1–2 and wait for `/api/health` to show the new commit. Then start the live test and push nothing until it ends: `curl -N $RENDER_URL/api/research/KOTAKBANK`, timestamping each event as in the 28 Oct test. Expected:
  - `event: done` within **8 min**
  - all four sections `ready`, or fixed reasons only
- [ ] **Step 2:** Confirm the save. `gh api repos/BoomingBrain/finn/contents/data/snapshot/dossiers/KOTAKBANK.json` returns 200. A second request replays in seconds, with no `progress` events.
- [ ] **Step 3:** Replace "10–30 minutes" in both components and the README with the measured figure, rounded up to the next whole minute range (e.g. "5–8 minutes"). Run `npx vitest run`. Expected: pass.
- [ ] **Step 4: Commit** `docs: measured live-build time`. Push, then `make deploy-space`.
