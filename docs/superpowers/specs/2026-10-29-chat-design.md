# FINN Chat — design

## Intent

The investor asks questions in their own words about their **holdings** and **companies FINN has already
researched**:
- "Is Polycab's debt a concern?"
- "Which of my holdings missed guidance?"
- "What's Pidilite's biggest segment?"

FINN answers from its research reports only, through retrieval (RAG). Every sentence cites a report source.
A company without a report gets **"Research pending for {name}"**, never an answer from outside knowledge.

**Why:** the brief asks for a point of view on how an investor interacts with FINN and to "try more than the
obvious". Chat over the investor's own researched universe lets them interrogate the reports without opening each
one, while keeping FINN's rule that every claim traces to a source.

## Goals

- Answer single-company and cross-company questions from the researched content.
- Ground every sentence in a retrieved report passage, with a chip that opens the cited page, as reports do now.
- Say "Research pending for {name}" when a question names an NSE company that has no report, with a link to start
  research.
- Answer in seconds.

## Non-goals and anti-goals

- **Not** answering from transcripts, annual-report pages or the web (user decision: reports only).
- **Not** general chat ("what's the market doing?"): FINN says the reports don't cover it.
- **Anti-goal:** an answer with a sentence that has no citation, or one that uses model knowledge about a
  company. This would be a failure even if the answer were right.

## Constraints

- Free tier: NVIDIA API (one key) for embeddings and answers; Render free for the API; static Space for the app.
- **Researched set:** every dossier in `data/snapshot/dossiers/`. That covers the 18 holdings, the demo set, the
  Nifty 50 prebuilds and anything saved from live research.
- The index stays current as dossiers are added or refreshed. Render ignores data-only commits, so it can't rely
  on its own checkout for fresh data.

## Approaches

| Approach | Trade-off |
|---|---|
| **Hybrid retrieval: keyword + meaning (chosen)** | Embeddings catch paraphrases ("leverage" ↔ "debt to equity"); keywords catch exact names and figures. Needs an embedding model, available free on the same NVIDIA key. |
| Keyword only (BM25) | Simplest, no embedding calls, but misses paraphrased questions. |
| Search full source pages too | Answers more, but the user chose reports only. |

The user chose **reports only**. Hybrid retrieval is the author's recommendation; the user didn't object.

## How it works

1. **Chunking (offline, `finn/rag.py`).** Each dossier becomes small self-contained passages, each tagged with
   `symbol`, `company`, the dossier `source_id`, and a citation `url` and `page`:
   - one snapshot passage per metric group: scale and growth, margins and returns, leverage and cash, red flags
   - one passage per Promised-vs-Delivered row (quote + delivered + verdict in plain words)
   - one per business description and one per segment
   - one per bull or bear point

   Every passage starts with the company name, so it reads on its own.
2. **Index (offline).** Embed every passage with NVIDIA's embedding model (`input_type: passage`) and write
   `data/snapshot/rag/index.json`: passages plus float16 vectors, base64-encoded.
   - Rebuilt by the jobs that change dossiers (dossier refresh, prebuild), and by a CLI.
   - Unchanged passages reuse cached embeddings.
   - Published with the site.
3. **Serving (Render).**
   - Loads the index from the Space URL at start and re-checks it every 30 minutes.
   - A dossier saved from live research is chunked and embedded into memory at once.
4. **Answering (`POST /api/chat`).**
   - **Find the companies named:**
     - match researched symbols and names in the question
     - an NSE company named but not researched → "Research pending for {name}" plus a research link (no model call)
     - no company named → search all researched content
     - **Call:** a follow-up that names no company carries the previous question's companies ("what about its
       margins?")
   - **Retrieve:** the top 12 passages by 0.6 × cosine + 0.4 × normalised BM25, restricted to the named companies
     if any, at most 4 per company when none are named.
   - **Answer:** the fast model, with FINN's grounding rules: at most 5 short sentences, each citing passage ids.
     Uncited sentences are dropped (`drop_uncited`).
   - **Nothing grounded** → "The reports don't cover that."
5. **The Chat screen.**
   - **Placement. Call:** a new bottom-bar tab, **Chat**, between Watch and Ask.
   - **Statement:** "Ask about your holdings and researched companies."
   - **Suggestion chips:** "Which holdings missed guidance?", "Is Polycab's debt a concern?", "Compare margins of
     Infosys and Persistent".
   - **The conversation:** newest at the bottom, kept per device for the visit.
   - **Answer points:** each with chips like "PIDILITIND AR p118" opening the cited page.
   - **Research-pending replies:** they link to Ask.
6. **Guards.**
   - 30 questions per IP an hour, plus the daily request budget.
   - Questions are 1–300 characters.
   - Errors use fixed copy.

## Left to the builder

- Passage wording.
- BM25 implementation: a small in-code scorer; no new dependency.
- Exact suggestion chips.
- **Embedding model, checked 29 Oct:** `nvidia/nemotron-3.5-embed-1b` answers in 1.4 s with 2,048-dimension
  vectors. The 8B model is 14 s, so not used. Estimated index: ~1,500 passages × 2,048 × float16 ≈ 6 MB, about 8 MB
  base64.
