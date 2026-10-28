"""Cross-checks each results card against screener.in's reported quarter, so an extraction error shows up as
"Unverified" instead of passing as fact."""
import logging
from typing import Callable

from finn.models import EnrichedAnnouncement, ResultsCard
from finn.sources.screener import CompanyData

log = logging.getLogger(__name__)

TOLERANCE = 0.02
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def crosscheck(card: ResultsCard, company: CompanyData) -> ResultsCard:
    """verified=True/False with mismatches, or None when there is nothing comparable (unreadable card, other basis,
    quarter not on screener yet). Lenders compare PAT only: screener's bank "Revenue" is interest earned, not NII."""
    if card.status != "ok" or card.period_end is None or card.basis != company.basis:
        return card.model_copy(update={"verified": None, "mismatches": []})
    label = f"{MONTHS[card.period_end.month - 1]} {card.period_end.year}"
    if label not in company.quarters.columns:
        return card.model_copy(update={"verified": None, "mismatches": []})
    col = company.quarters.columns.index(label)
    pairs = [("PAT", ("Net Profit",))] if card.layout == "lender" else [("Revenue", ("Sales", "Revenue")),
                                                                         ("PAT", ("Net Profit",))]
    mismatches, compared = [], 0
    for metric, rows in pairs:
        row = company.quarters.row(*rows)
        ours = card.metrics.get(metric)
        theirs = row[col] if row else None
        if ours is None or theirs is None:
            continue
        compared += 1
        if abs(ours.current - theirs) > TOLERANCE * max(abs(theirs), 1.0):
            mismatches.append(metric)
    if compared == 0:
        return card.model_copy(update={"verified": None, "mismatches": []})
    return card.model_copy(update={"verified": not mismatches, "mismatches": mismatches})


def apply_crosscheck(items: list[EnrichedAnnouncement], fetch_company: Callable[[str], CompanyData]) -> None:
    """Cross-checks every readable results card in place. A symbol whose screener page can't be fetched keeps
    verified=None; ingestion still publishes."""
    companies: dict[str, CompanyData | None] = {}
    for item in items:
        if not item.results or item.results.status != "ok":
            continue
        symbol = item.announcement.symbol
        if symbol not in companies:
            try:
                companies[symbol] = fetch_company(symbol)
            except Exception as e:
                log.warning("screener cross-check skipped for %s: %r", symbol, e)
                companies[symbol] = None
        if companies[symbol]:
            item.results = crosscheck(item.results, companies[symbol])
