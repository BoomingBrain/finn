"""The Render service. It exists only for live research on tickers without a precomputed dossier;
everything else is served as static files from the Hugging Face Space. A finished live dossier is committed to the
repo (finn.persist), so it is built once and becomes a static, instant dossier after the next deploy."""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator, Callable

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from finn.guard import RateLimiter, nse_symbols
from finn.llm import LLM, BudgetExceeded, RequestBudget
from finn.persist import GitHubStore
from finn.pull.chat import NOT_COVERED, RELEVANCE_MIN, answer, chip_label
from finn.pull.dossier import Dossier, SectionEvent, build_dossier, needs_build
from finn.rag import Embedder, Index, chunk_dossier, find_companies
from finn.research_hub import Build, ResearchHub
from finn.snapshot import SnapshotStore
from finn.sources.screener import CompanyNotFound, SourceUnreachable

log = logging.getLogger(__name__)
LOCAL_DEV_ORIGIN = "http://localhost:5173"
KEEPALIVE_SECONDS = 15
INDEX_REFRESH_SECONDS = 30 * 60  # a comment line while a section is still building, so proxies keep the stream open


def _sse(data: dict | str, event: str | None = None) -> str:
    body = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return (f"event: {event}\n" if event else "") + f"data: {body}\n\n"


def _force_fail(symbol: str):
    raise SourceUnreachable(f"{symbol}: FINN_FORCE_SOURCE_FAIL is set")


class ChatRequest(BaseModel):
    question: str
    context: list[str] = []


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def create_app(store: SnapshotStore | None = None, build: Callable[..., AsyncIterator[SectionEvent]] = build_dossier,
               limiter: RateLimiter | None = None, budget: RequestBudget | None = None,
               llm: LLM | None = None, saved: GitHubStore | None = None, index: Index | None = None,
               embedder=None, chat_limiter: RateLimiter | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        if state["index"] is None and not origins:  # local run: the index file in this checkout
            saved_index = store.load_rag_index()
            state["index"] = Index.from_dict(saved_index) if saved_index else None
        loader = asyncio.create_task(keep_index_fresh()) if state["index"] is None and origins else None
        yield
        if loader:
            loader.cancel()

    app = FastAPI(title="FINN research API", docs_url=None, redoc_url=None, lifespan=lifespan)
    origins = [o.strip() for o in os.environ.get("WEB_ORIGIN", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins + [LOCAL_DEV_ORIGIN], allow_methods=["GET", "POST"],
                       allow_headers=["*"])
    store = store or SnapshotStore()
    limiter = limiter or RateLimiter(per_hour=int(os.environ.get("LIVE_RESEARCH_PER_IP_PER_HOUR", "20")))
    budget = budget or RequestBudget(daily_requests=int(os.environ.get("DAILY_LLM_REQUEST_BUDGET", "1500")))
    saved = saved or GitHubStore.from_env()  # live dossiers, kept permanently in the repo
    live: dict[str, list[dict]] = {}  # finished live dossiers, for the life of the process
    chat_limiter = chat_limiter or RateLimiter(per_hour=int(os.environ.get("CHAT_PER_IP_PER_HOUR", "30")))
    state = {"llm": llm, "index": index, "embedder": embedder}

    def get_embedder():
        if state["embedder"] is None:
            state["embedder"] = Embedder()
        return state["embedder"]

    async def keep_index_fresh():
        """The chat index ships with the static site; Render ignores data-only commits, so it fetches it."""
        url = f"{origins[0].rstrip('/')}/data/rag/index.json"
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            while True:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    fresh = Index.from_dict(r.json())
                    if state["index"] is not None:  # keep dossiers saved live since the site was built
                        extra = [p for p in state["index"].passages if p.symbol not in fresh.symbols]
                        if extra:
                            rows = [i for i, p in enumerate(state["index"].passages) if p.symbol not in fresh.symbols]
                            fresh.add(extra, state["index"].vectors[rows])
                    state["index"] = fresh
                    log.info("chat index loaded: %d passages", len(fresh.passages))
                except Exception as e:
                    log.warning("chat index refresh failed: %r", e)
                await asyncio.sleep(INDEX_REFRESH_SECONDS)


    def get_llm() -> LLM:
        if state["llm"] is None:  # created on first live build, so health checks need no key
            state["llm"] = LLM(budget=budget)
        return state["llm"]

    @app.get("/api/health")
    def health() -> dict:
        # Render sets RENDER_GIT_COMMIT: shows which commit is live (data-only ingest commits shouldn't redeploy)
        return {"ok": True, "service": "finn-research", "commit": os.environ.get("RENDER_GIT_COMMIT", "")[:7] or None}

    def replay(sections: list[dict]) -> StreamingResponse:
        async def stream():
            for s in sections:
                yield _sse(s)
            yield _sse("{}", event="done")
        return StreamingResponse(stream(), media_type="text/event-stream")

    async def remember(symbol: str, sections: list[SectionEvent]) -> None:
        """A finished build: replay it from memory, and keep it permanently unless a section failed."""
        sent = [e.model_dump(mode="json") for e in sections]
        live[symbol] = sent
        snap = (sent[0].get("data") or {}) if sent else {}
        dossier = Dossier(symbol=symbol, name=snap.get("name", symbol), basis=snap.get("basis", ""),
                          built_at=datetime.now(timezone.utc), sources=snap.get("sources", {}),
                          sections=sections).model_dump(mode="json")
        if needs_build(dossier) is None:  # never persist a dossier with a failed section; the daily job retries
            await asyncio.to_thread(saved.save, symbol, dossier)
            if state["index"] is not None:  # chat can answer about it straight away
                try:
                    passages = chunk_dossier(dossier)
                    vectors = await asyncio.to_thread(get_embedder().embed, [p.text for p in passages], "passage")
                    state["index"].add(passages, vectors)
                except Exception as e:
                    log.warning("adding %s to the chat index failed: %r", symbol, e)

    def run_build(symbol: str, report: Callable[[dict], None]) -> AsyncIterator[SectionEvent]:
        kwargs = {"fetch_company": _force_fail} if os.environ.get("FINN_FORCE_SOURCE_FAIL") else {}
        return build(symbol, get_llm(), progress=report, **kwargs)

    hub = ResearchHub(run_build, concurrency=int(os.environ.get("LIVE_RESEARCH_CONCURRENCY", "2")),
                      on_complete=remember)

    def error_event(symbol: str, e: Exception) -> str:
        if isinstance(e, SourceUnreachable):
            return _sse({"code": "sources_unreachable",
                         "message": f"Couldn't fetch sources for {symbol} from the server."}, event="error")
        if isinstance(e, CompanyNotFound):
            return _sse({"code": "not_found", "message": f"FINN can't find {symbol} on screener.in."}, event="error")
        if isinstance(e, BudgetExceeded):
            return _sse({"code": "budget_exhausted", "message": "Today's AI budget for live research is used up."},
                        event="error")
        return _sse({"code": "failed", "message": f"Research on {symbol} stopped unexpectedly: {type(e).__name__}."},
                    event="error")

    async def follow(symbol: str, b: Build) -> AsyncIterator[str]:
        """Streams one viewer's view of a shared build. Leaving stops the stream, not the build."""
        q = b.listen()
        try:
            while True:
                try:
                    kind, item = await asyncio.wait_for(q.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": building\n\n"
                    continue
                if kind == "queued":
                    yield _sse(item, event="queued")
                elif kind == "progress":
                    yield _sse(item, event="progress")
                elif kind == "section":
                    yield _sse(item.model_dump(mode="json"))
                elif kind == "end":
                    yield _sse("{}", event="done")
                    return
                else:
                    yield error_event(symbol, item)
                    return
        finally:
            b.leave(q)

    def stream(symbol: str, b: Build) -> StreamingResponse:
        return StreamingResponse(follow(symbol, b), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/research/{symbol}")
    async def research(symbol: str, request: Request):
        symbol = symbol.upper()
        precomputed = store.load_dossier(symbol)
        if precomputed:
            return replay(precomputed["sections"])
        if symbol not in nse_symbols():
            return JSONResponse({"error": "unknown_symbol"}, status_code=404)
        if symbol in live:
            return replay(live[symbol])
        kept = await asyncio.to_thread(saved.load, symbol)  # built live earlier, not yet on the static site
        if kept:
            live[symbol] = kept["sections"]
            return replay(kept["sections"])
        running = hub.get(symbol)
        if running:  # someone already asked: join that build instead of starting another
            return stream(symbol, running)
        if not limiter.allow(_client_ip(request), now=time.time()):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            budget.check()
        except BudgetExceeded:
            return JSONResponse({"error": "budget_exhausted"}, status_code=429)
        return stream(symbol, hub.start(symbol))

    @app.post("/api/chat")
    async def chat(body: ChatRequest, request: Request):
        question = body.question.strip()
        if not 1 <= len(question) <= 300:
            return JSONResponse({"error": "bad_question"}, status_code=400)
        idx: Index | None = state["index"]
        if idx is None:
            return JSONResponse({"error": "index_loading"}, status_code=503)
        if not chat_limiter.allow(_client_ip(request), now=time.time()):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            budget.check()
        except BudgetExceeded:
            return JSONResponse({"error": "budget_exhausted"}, status_code=429)

        nse = nse_symbols()
        researched = {sym: nse.get(sym, sym) for sym in idx.symbols}
        found, pending = find_companies(question, researched, nse)
        if not found:  # a follow-up: "what about its margins?", even if it also names an unresearched company
            found = [s for s in body.context if s in researched]
        out = {"points": [], "citations": [], "symbols": found, "not_covered": False,
               "pending": [{"symbol": s, "name": n} for s, n in pending]}
        if pending and not found:
            return out  # only unresearched companies: nothing to retrieve, no model call

        query_vec = (await asyncio.to_thread(get_embedder().embed, [question], "query"))[0]
        if not found and idx.best_cosine(query_vec) < RELEVANCE_MIN:  # off-topic: no model call
            out.update(not_covered=True, points=[{"text": NOT_COVERED, "source_ids": []}])
            return out
        passages = idx.search(query_vec, question, symbols=set(found) or None)
        points = await asyncio.to_thread(answer, question, passages, get_llm())
        if not points:
            out.update(not_covered=True, points=[{"text": NOT_COVERED, "source_ids": []}])
            return out
        by_id = {p.id: p for p in passages}
        cited = list(dict.fromkeys(i for p in points for i in p.source_ids))
        out["points"] = [p.model_dump() for p in points]
        out["citations"] = [{"source_id": i, "url": by_id[i].url, "page": by_id[i].page,
                             "label": f"{by_id[i].symbol} {chip_label(by_id[i].source_id)}"} for i in cited]
        out["symbols"] = found or sorted({by_id[i].symbol for i in cited})
        return out

    @app.get("/", include_in_schema=False)
    def root():
        # This service has no pages of its own; send people who open its URL to the app.
        if origins:
            return RedirectResponse(origins[0])
        return {"service": "finn-research", "app": "not configured"}

    return app


app = create_app()
