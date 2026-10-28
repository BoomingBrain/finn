"""The research dossier, built section by section in a fixed order: snapshot, Promised vs Delivered, business,
bull vs bear. A failing section becomes `unavailable` with fixed copy; the others still arrive.

CLI: `uv run python -m finn.pull.dossier --all` (or `--symbols A,B`) writes data/snapshot/dossiers/."""
import argparse
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Literal

from pydantic import BaseModel

from finn.guard import write_symbols
from finn.llm import LLM, BudgetExceeded
from finn.portfolio import load_portfolio
from finn.pull.guidance import DeliveryRow, assess_delivery, extract_targets
from finn.pull.metrics import compute_snapshot
from finn.pull.sections import BusinessSnapshot, Citation, bull_bear, business_snapshot, page_of
from finn.snapshot import SnapshotStore
from finn.sources.documents import DocText, fetch_pdf_text
from finn.sources.screener import BASE, CompanyData, fetch_company

log = logging.getLogger(__name__)

NO_TRANSCRIPTS = "No concall transcripts on screener.in"
NO_ANNUAL_REPORT = "No annual report on screener.in"
NO_TEXT = "Source document has no extractable text"
BUDGET = "Daily AI budget reached"
FAILED = "Analysis failed"
TRANSCRIPTS_USED = 4


class SectionEvent(BaseModel):
    section: Literal["snapshot", "delivery", "business", "bull_bear"]
    status: Literal["ready", "unavailable"]
    reason: str | None = None
    data: dict | None = None
    citations: list[Citation] = []


class Dossier(BaseModel):
    symbol: str
    name: str
    built_at: datetime
    basis: str
    sections: list[SectionEvent]


class _NoText(Exception):
    pass


def _unavailable(section, e: Exception) -> SectionEvent:
    if isinstance(e, BudgetExceeded):
        reason = BUDGET
    elif isinstance(e, _NoText):
        reason = NO_TEXT
    else:
        log.warning("%s section failed: %r", section, e)
        reason = FAILED
    return SectionEvent(section=section, status="unavailable", reason=reason)


def _citations(ids, urls: dict[str, str]) -> list[Citation]:
    """One citation per distinct id; the url comes from the id's document prefix."""
    out = {}
    for sid in ids:
        prefix = sid.rsplit(":p", 1)[0] if sid != "SCR" else "SCR"
        if sid not in out and prefix in urls:
            out[sid] = Citation(source_id=sid, url=urls[prefix], page=page_of(sid))
    return list(out.values())


async def _delivery(c: CompanyData, llm: LLM, fetch_text, urls: dict[str, str]) -> list[DeliveryRow]:
    transcripts = [t for t in c.transcripts if t.date][:TRANSCRIPTS_USED]
    if not transcripts:
        raise LookupError(NO_TRANSCRIPTS)

    def one(link):
        try:
            doc = fetch_text(link.url)
        except Exception as e:  # one unreachable transcript shouldn't sink the other three
            log.warning("transcript %s unavailable: %r", link.url, e)
            return None
        if not doc.readable:
            return None
        urls[f"T:{link.date.isoformat()}"] = link.url
        return extract_targets(doc, link.date, llm)

    results = await asyncio.gather(*(asyncio.to_thread(one, t) for t in transcripts))
    if all(r is None for r in results):
        raise _NoText()
    targets = [t for r in results if r for t in r]
    return await asyncio.to_thread(assess_delivery, targets, c.quarters, llm)


async def _business(c: CompanyData, llm: LLM, fetch_text, urls: dict[str, str]) -> BusinessSnapshot | None:
    reports = sorted((a for a in c.annual_reports if a.date), key=lambda a: a.date, reverse=True)
    if not reports:
        raise LookupError(NO_ANNUAL_REPORT)
    report = reports[0]
    doc = await asyncio.to_thread(fetch_text, report.url)
    if not doc.readable:
        raise _NoText()
    label = str(report.date.year)
    urls[f"AR:{label}"] = report.url
    return await asyncio.to_thread(business_snapshot, doc, label, llm)


async def build_dossier(symbol: str, llm: LLM, fetch_company: Callable[[str], CompanyData] = fetch_company,
                        fetch_text: Callable[[str], DocText] = fetch_pdf_text) -> AsyncIterator[SectionEvent]:
    """Yields the four sections in order. `CompanyNotFound` / `SourceUnreachable` from fetch_company propagate
    before anything is yielded, so the caller can answer 404 or a sources error."""
    c = await asyncio.to_thread(fetch_company, symbol)
    path = f"/company/{c.symbol}/consolidated/" if c.basis == "consolidated" else f"/company/{c.symbol}/"
    urls = {"SCR": BASE + path}

    snapshot = compute_snapshot(c)
    yield SectionEvent(section="snapshot", status="ready",
                       data={"name": c.name, "about": c.about[:600], "basis": c.basis, **snapshot.model_dump()},
                       citations=_citations(["SCR"], urls))

    delivery: list[DeliveryRow] = []
    try:
        delivery = await _delivery(c, llm, fetch_text, urls)
        yield SectionEvent(section="delivery", status="ready",
                           data={"transcripts": [t.label for t in c.transcripts[:TRANSCRIPTS_USED]],
                                 "rows": [r.model_dump(mode="json") for r in delivery]},
                           citations=_citations([r.target.source_id for r in delivery], urls))
    except LookupError as e:
        yield SectionEvent(section="delivery", status="unavailable", reason=str(e.args[0]))
    except Exception as e:
        yield _unavailable("delivery", e)

    business = None
    try:
        business = await _business(c, llm, fetch_text, urls)
        if business is None:
            raise ValueError("no grounded business description")
        ids = business.source_ids + [i for s in business.segments for i in s.source_ids]
        yield SectionEvent(section="business", status="ready", data=business.model_dump(),
                           citations=_citations(ids, urls))
    except LookupError as e:
        yield SectionEvent(section="business", status="unavailable", reason=str(e.args[0]))
    except Exception as e:
        yield _unavailable("business", e)

    try:
        bb = await asyncio.to_thread(bull_bear, snapshot, delivery, business, llm)
        ids = [i for p in bb.bull + bb.bear for i in p.source_ids]
        yield SectionEvent(section="bull_bear", status="ready", data=bb.model_dump(),
                           citations=_citations(ids, urls))
    except Exception as e:
        yield _unavailable("bull_bear", e)


async def collect_dossier(symbol: str, llm: LLM, **kwargs) -> Dossier:
    sections = [s async for s in build_dossier(symbol, llm, **kwargs)]
    snap = sections[0].data or {}
    return Dossier(symbol=symbol.upper(), name=snap.get("name", symbol), basis=snap.get("basis", ""),
                   built_at=datetime.now(timezone.utc), sections=sections)


def demo_symbols() -> list[str]:
    p = load_portfolio()
    return [h.symbol for h in p.holdings] + list(p.research)


def needs_build(existing: dict | None, retry_failed: bool) -> bool:
    """With retry_failed, rebuild only dossiers that are missing or have a section that failed transiently
    (a missing source such as "No concall transcripts" is a real answer, not a failure)."""
    if existing is None or not retry_failed:
        return True
    return any(s.get("reason") in (FAILED, BUDGET) for s in existing.get("sections", []))


async def _precompute(symbols: list[str], store: SnapshotStore, llm: LLM, skip_existing: bool, parallel: int,
                      retry_failed: bool = False):
    gate = asyncio.Semaphore(parallel)

    async def one(symbol: str):
        existing = store.load_dossier(symbol)
        if (skip_existing and existing) or not needs_build(existing, retry_failed):
            return
        async with gate:
            started = datetime.now()
            try:
                d = await collect_dossier(symbol, llm)
            except Exception as e:
                log.error("%s: dossier failed: %r", symbol, e)
                return
            store.save_dossier(symbol, d.model_dump(mode="json"))
            states = " ".join(f"{s.section}={s.status}" for s in d.sections)
            log.info("%s done in %.0fs: %s", symbol, (datetime.now() - started).total_seconds(), states)

    await asyncio.gather(*(one(s) for s in symbols))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="Precompute research dossiers")
    parser.add_argument("--all", action="store_true", help="every holding plus the research demo tickers")
    parser.add_argument("--symbols", help="comma-separated tickers")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--retry-failed", action="store_true", help="rebuild only missing or failed dossiers")
    parser.add_argument("--parallel", type=int, default=3)
    args = parser.parse_args()
    symbols = demo_symbols() if args.all else [s.strip().upper() for s in (args.symbols or "").split(",") if s.strip()]
    if not symbols:
        parser.error("pass --all or --symbols")
    store = SnapshotStore()
    asyncio.run(_precompute(symbols, store, LLM(), args.skip_existing, args.parallel, args.retry_failed))
    write_symbols(store)
    print(LLM().usage())


if __name__ == "__main__":
    main()
