"""Fetch -> classify -> enrich -> write data/snapshot (push.json for state, events.json for the browser).
Incremental: announcements already in push.json are never re-processed.

Usage: uv run python -m finn.ingest [--symbols INFY HDFCBANK] [--days 7]"""
import argparse
import logging
from datetime import datetime, timedelta

from pydantic import BaseModel

from finn.llm import LLM
from finn.models import IST, EventsFile, PushSnapshot
from finn.portfolio import load_portfolio
from finn.push.classify import classify
from finn.push.enrich import enrich
from finn.push.events import to_event
from finn.snapshot import SnapshotStore
from finn.sources.announcements import fetch_announcements

log = logging.getLogger(__name__)
RETAIN_DAYS = 60


class IngestReport(BaseModel):
    fetched: int
    new: int
    enriched: int
    failed_sources: list[str]


def ingest(symbols: list[str] | None, days: int, store: SnapshotStore, llm: LLM, now: datetime,
           fetch=fetch_announcements, enrich_fn=enrich) -> IngestReport:
    portfolio = load_portfolio()
    holdings = [h for h in portfolio.holdings if not symbols or h.symbol in symbols]
    result = fetch(holdings, (now - timedelta(days=days)).date(), now.date())

    previous = store.load_push()
    known = {e.announcement.id: e for e in (previous.announcements if previous else [])}
    new = [a for a in result.items if a.id not in known]
    categories = classify(new, llm) if new else {}
    enriched = []
    for a in new:
        holding = portfolio.holding(a.symbol)
        enriched.append(enrich_fn(a, categories[a.id], llm, sector=holding.sector if holding else None))

    cutoff = now - timedelta(days=RETAIN_DAYS)
    items = [e for e in [*known.values(), *enriched] if e.announcement.filed_at >= cutoff]
    items.sort(key=lambda e: e.announcement.filed_at, reverse=True)
    store.save_push(PushSnapshot(as_of=now, announcements=items, failed_sources=[f"nse:{s}" for s in result.failed]))
    store.save_events(EventsFile(as_of=now, events=[to_event(e) for e in items]))
    return IngestReport(fetched=len(result.items), new=len(new),
                        enriched=sum(1 for e in enriched if e.results or e.summary or e.profile),
                        failed_sources=result.failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, classify and enrich portfolio announcements.")
    parser.add_argument("--symbols", nargs="*", help="limit to these holdings (default: all)")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    llm = LLM()
    report = ingest(args.symbols, args.days, SnapshotStore(), llm, datetime.now(IST))
    print(report.model_dump_json(indent=1))
    print("LLM usage:", llm.usage())


if __name__ == "__main__":
    main()
