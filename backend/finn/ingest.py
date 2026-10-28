"""Fetch -> classify -> enrich -> write data/snapshot (push.json for state, events.json for the browser).
Incremental: announcements already in push.json are never re-processed.

Usage: uv run python -m finn.ingest [--symbols INFY HDFCBANK] [--days 7] [--reprocess results management_change]
--reprocess re-enriches stored filings of those categories (after improving enrichment); the LLM cache keeps
unchanged prompts free."""
import argparse
import logging
from datetime import datetime, timedelta

from pydantic import BaseModel

from finn.llm import LLM
from finn.models import IST, EventsFile, PushSnapshot
from finn.portfolio import load_portfolio
from finn.push.classify import classify, classify_rule
from finn.push.enrich import enrich
from finn.push.cluster import cluster_events
from finn.snapshot import SnapshotStore
from finn.sources.announcements import fetch_announcements
from finn.sources.prices import fetch_eod

log = logging.getLogger(__name__)
RETAIN_DAYS = 60


class IngestReport(BaseModel):
    fetched: int
    new: int
    enriched: int
    failed_sources: list[str]


def ingest(symbols: list[str] | None, days: int, store: SnapshotStore, llm: LLM, now: datetime,
           fetch=fetch_announcements, enrich_fn=enrich, fetch_prices=fetch_eod,
           reprocess: frozenset[str] = frozenset()) -> IngestReport:
    portfolio = load_portfolio()
    holdings = [h for h in portfolio.holdings if not symbols or h.symbol in symbols]
    result = fetch(holdings, (now - timedelta(days=days)).date(), now.date())

    previous = store.load_push()
    stored = previous.announcements if previous else []
    known = {e.announcement.id: e for e in stored if e.category not in reprocess}
    redo = {e.announcement.id: e for e in stored if e.category in reprocess}  # re-enrich, keep the category
    fresh = [a for a in result.items if a.id not in known and a.id not in redo]
    categories = classify(fresh, llm) if fresh else {}
    # Rules are deterministic and authoritative; a stored LLM label is kept only where no rule applies.
    categories.update({i: classify_rule(e.announcement.subject, e.announcement.raw_category,
                                        e.announcement.attachment_url) or e.category for i, e in redo.items()})
    new = fresh + [e.announcement for e in redo.values()]
    enriched = []
    for a in new:
        holding = portfolio.holding(a.symbol)
        enriched.append(enrich_fn(a, categories[a.id], llm, sector=holding.sector if holding else None))

    cutoff = now - timedelta(days=RETAIN_DAYS)
    items = [e for e in [*known.values(), *enriched] if e.announcement.filed_at >= cutoff]
    items.sort(key=lambda e: e.announcement.filed_at, reverse=True)
    store.save_push(PushSnapshot(as_of=now, announcements=items, failed_sources=[f"nse:{s}" for s in result.failed]))
    prices = store.load_prices()
    try:
        prices.update(fetch_prices([h.symbol for h in holdings], now=now))
        store.save_prices(prices)
    except Exception as e:  # keep the last good prices; events still publish
        log.warning("price fetch failed: %s", e)
    store.save_events(EventsFile(as_of=now, events=cluster_events(items, prices)))
    return IngestReport(fetched=len(result.items), new=len(new),
                        enriched=sum(1 for e in enriched if e.results or e.summary or e.profile),
                        failed_sources=result.failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, classify and enrich portfolio announcements.")
    parser.add_argument("--symbols", nargs="*", help="limit to these holdings (default: all)")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--reprocess", nargs="*", default=[], help="re-enrich stored filings of these categories")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    llm = LLM()
    report = ingest(args.symbols, args.days, SnapshotStore(), llm, datetime.now(IST),
                    reprocess=frozenset(args.reprocess))
    print(report.model_dump_json(indent=1))
    print("LLM usage:", llm.usage())


if __name__ == "__main__":
    main()
