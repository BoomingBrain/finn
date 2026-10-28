"""The Render service. It exists only for live research on tickers without a precomputed dossier;
everything else is served as static files from the Hugging Face Space."""
import asyncio
import json
import os
import time
from typing import AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from finn.guard import RateLimiter, nse_symbols
from finn.llm import LLM, BudgetExceeded, RequestBudget
from finn.pull.dossier import SectionEvent, build_dossier
from finn.snapshot import SnapshotStore
from finn.sources.screener import CompanyNotFound, SourceUnreachable

LOCAL_DEV_ORIGIN = "http://localhost:5173"
KEEPALIVE_SECONDS = 15  # a comment line while a section is still building, so proxies keep the stream open


def _sse(data: dict | str, event: str | None = None) -> str:
    body = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return (f"event: {event}\n" if event else "") + f"data: {body}\n\n"


def _force_fail(symbol: str):
    raise SourceUnreachable(f"{symbol}: FINN_FORCE_SOURCE_FAIL is set")


def create_app(store: SnapshotStore | None = None, build: Callable[..., AsyncIterator[SectionEvent]] = build_dossier,
               limiter: RateLimiter | None = None, budget: RequestBudget | None = None,
               llm: LLM | None = None) -> FastAPI:
    app = FastAPI(title="FINN research API", docs_url=None, redoc_url=None)
    origins = [o.strip() for o in os.environ.get("WEB_ORIGIN", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins + [LOCAL_DEV_ORIGIN], allow_methods=["GET"],
                       allow_headers=["*"])
    store = store or SnapshotStore()
    limiter = limiter or RateLimiter(per_hour=int(os.environ.get("LIVE_RESEARCH_PER_IP_PER_HOUR", "3")))
    budget = budget or RequestBudget(daily_requests=int(os.environ.get("DAILY_LLM_REQUEST_BUDGET", "1500")))
    live: dict[str, list[dict]] = {}  # finished live dossiers, for the life of the process
    state = {"llm": llm}

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

    async def live_stream(symbol: str) -> AsyncIterator[str]:
        kwargs = {"fetch_company": _force_fail} if os.environ.get("FINN_FORCE_SOURCE_FAIL") else {}
        sections = build(symbol, get_llm(), **kwargs)
        sent = []
        try:
            while True:
                step = asyncio.ensure_future(anext(sections))
                while not step.done():
                    await asyncio.wait({step}, timeout=KEEPALIVE_SECONDS)
                    if not step.done():
                        yield ": building\n\n"
                try:
                    event = step.result()
                except StopAsyncIteration:
                    break
                sent.append(event.model_dump(mode="json"))
                yield _sse(sent[-1])
        except SourceUnreachable:
            yield _sse({"code": "sources_unreachable",
                        "message": f"Couldn't fetch sources for {symbol} from the server."}, event="error")
            return
        except CompanyNotFound:
            yield _sse({"code": "not_found", "message": f"FINN can't find {symbol} on screener.in."}, event="error")
            return
        except BudgetExceeded:
            yield _sse({"code": "budget_exhausted", "message": "Today's AI budget for live research is used up."},
                       event="error")
            return
        live[symbol] = sent
        yield _sse("{}", event="done")

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
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
        if not limiter.allow(ip, now=time.time()):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            budget.check()
        except BudgetExceeded:
            return JSONResponse({"error": "budget_exhausted"}, status_code=429)
        return StreamingResponse(live_stream(symbol), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/", include_in_schema=False)
    def root():
        # This service has no pages of its own; send people who open its URL to the app.
        if origins:
            return RedirectResponse(origins[0])
        return {"service": "finn-research", "app": "not configured"}

    return app


app = create_app()
