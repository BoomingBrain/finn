"""The LLM-written dossier sections and the citation guard. Every prompt starts with GROUNDING_RULES, and every
item the model returns must cite source ids that were actually sent, or it is dropped."""
import re
from typing import Callable, TypeVar

from pydantic import BaseModel

from finn.llm import LLM
from finn.pull.guidance import DeliveryRow
from finn.pull.metrics import FinancialSnapshot
from finn.sources.documents import DocText

T = TypeVar("T")

GROUNDING_RULES = ("Use only the numbered sources provided. Do not use outside knowledge of this company, news, or "
                   "analyst views. Every claim must cite at least one source id exactly as given. If the sources do "
                   "not support an answer, return an empty list.")


class Citation(BaseModel):
    source_id: str  # "T:{YYYY-MM-DD}:p{n}" | "AR:{label}:p{n}" | "SCR"
    url: str
    page: int | None


class Point(BaseModel):
    text: str
    source_ids: list[str] = []


class Segment(BaseModel):
    name: str
    share_pct: float | None = None
    source_ids: list[str] = []


class BusinessSnapshot(BaseModel):
    what_it_does: str = ""
    segments: list[Segment] = []
    source_ids: list[str] = []


class BullBear(BaseModel):
    bull: list[Point] = []
    bear: list[Point] = []


def _clean(ids: list[str]) -> list[str]:
    return [i.strip(" []") for i in ids]


def drop_uncited(items: list[T], valid_ids: set[str], key: Callable[[T], list[str]]) -> list[T]:
    """Items that cite at least one source id, all of which were provided."""
    return [item for item in items if key(item) and all(i in valid_ids for i in key(item))]


def page_of(source_id: str) -> int | None:
    m = re.search(r":p(\d+)$", source_id)
    return int(m.group(1)) if m else None


# ---- business --------------------------------------------------------------------------------------------------

_BUSINESS_KEYWORDS = ("segment", "business overview", "revenue mix", "products", "our business", "brands",
                      "market share", "categories")
# BRSR's "Details of business activities (accounting for 90% of the turnover)" is in every listed company's annual
# report (sometimes after the financial statements) and gives each business's share of turnover.
_BRSR_ACTIVITIES = "description of business activity"
_BUSINESS_PROMPT = """From the annual report pages below, describe the business.
Return JSON: {{"what_it_does": "2-3 plain sentences on what the company sells and to whom", "source_ids": [...],
"segments": [{{"name": "...", "share_pct": <% of revenue as printed, or null>, "source_ids": [...]}}]}}
List at most 6 segments. Give share_pct only if the page prints it.

{pages}"""


def business_pages(ar: DocText, n: int = 8) -> list[int]:
    """1-based page numbers of the narrative pages that talk most about the business. Pages from the first auditor's
    report on are financial statements, whose segment notes would otherwise win. The contents page also names the
    auditor's report (pages 2-4 in ITC, TITAN, HAL...), so mentions in the first 10% of the report don't count."""
    lowered = [p.lower() for p in ar.pages]
    start = len(lowered) // 10
    end = next((i for i, p in enumerate(lowered) if i >= start and "independent auditor" in p), len(lowered))
    brsr = next((i + 1 for i, p in enumerate(lowered) if _BRSR_ACTIVITIES in p), None)
    scored = [(sum(p.count(k) for k in _BUSINESS_KEYWORDS), i + 1) for i, p in enumerate(lowered[:end])
              if i + 1 != brsr]
    ranked = sorted(scored, key=lambda x: (-x[0], x[1]))  # ties go to the earlier (overview) page
    narrative = [page for hits, page in ranked[:n - (1 if brsr else 0)] if hits > 0]
    return sorted(narrative + ([brsr] if brsr else []))


def _number_on_page(value: float, pages: list[str]) -> bool:
    text = " ".join(pages)
    forms = {f"{value:g}", f"{value:.1f}", f"{round(value)}"}
    return any(re.search(rf"(?<![\d.]){re.escape(f)}\s*%", text) for f in forms)


def business_snapshot(ar: DocText, ar_label: str, llm: LLM) -> BusinessSnapshot | None:
    """Bulk tier over the ~8 most relevant pages. None if nothing grounded comes back. A segment share that isn't
    printed on its cited pages is blanked."""
    pages = {f"AR:{ar_label}:p{n}": ar.pages[n - 1][:3500] for n in business_pages(ar)}
    if not pages:
        return None
    blocks = "\n\n".join(f"[{sid}]\n{text.strip()}" for sid, text in pages.items())
    reply = llm.complete_json("bulk", GROUNDING_RULES, _BUSINESS_PROMPT.format(pages=blocks), BusinessSnapshot,
                              max_tokens=1500)
    reply.source_ids = _clean(reply.source_ids)
    for s in reply.segments:
        s.source_ids = _clean(s.source_ids)
    valid = set(pages)
    segments = drop_uncited(reply.segments, valid, key=lambda s: s.source_ids)[:6]
    for s in segments:
        if s.share_pct is not None and not _number_on_page(s.share_pct, [pages[i] for i in s.source_ids]):
            s.share_pct = None
    if not reply.what_it_does.strip() or not drop_uncited([reply], valid, key=lambda r: r.source_ids):
        return None
    return BusinessSnapshot(what_it_does=reply.what_it_does.strip(), segments=segments, source_ids=reply.source_ids)


# ---- bull vs bear ----------------------------------------------------------------------------------------------

_BULL_BEAR_PROMPT = """Write the bull case and the bear case for an investor from the sources below.
At most 3 points each, one sentence each, specific and numeric where the source allows.
Return JSON: {{"bull": [{{"text": "...", "source_ids": [...]}}], "bear": [...]}}

{sources}"""


def _cr(v: float | None) -> str:
    return "n/a" if v is None else f"₹{v:,.0f} Cr"


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:g}%"


def snapshot_text(s: FinancialSnapshot) -> str:
    lines = [f"Revenue TTM {_cr(s.revenue_ttm)}, PAT TTM {_cr(s.pat_ttm)}",
             f"3-year CAGR: revenue {_pct(s.revenue_cagr_3y)}, PAT {_pct(s.pat_cagr_3y)}"]
    if not s.lender:
        lines += [f"Operating margin {_pct(s.opm_latest)} (3 years ago {_pct(s.opm_3y_ago)}), ROCE {_pct(s.roce_latest)}",
                  f"Debt to equity {s.debt_to_equity if s.debt_to_equity is not None else 'n/a'}, "
                  f"operating cash flow / PAT over 3 years {s.cfo_to_pat_3y if s.cfo_to_pat_3y is not None else 'n/a'}"]
    lines.append(f"ROE {_pct(s.roe_latest)}")
    quarters = ", ".join(f"{q.label}: revenue {_cr(q.revenue)}, PAT {_cr(q.pat)}" for q in s.quarterly[-4:])
    lines.append(f"Last quarters: {quarters}")
    if s.flags:
        lines.append("Flags: " + "; ".join(s.flags))
    return "\n".join(lines)


# Plain words for the model: a raw "not_checkable" was read as "not delivered" (Bharti Airtel, 28 Oct).
VERDICT_WORDS = {"met": "met", "partly": "partly met", "missed": "missed",
                 "pending": "in progress (the period is not over yet)",
                 "not_checkable": "cannot be checked from reported financials; this says nothing about delivery"}


def bull_bear(snapshot: FinancialSnapshot, delivery: list[DeliveryRow], business: BusinessSnapshot | None,
              llm: LLM) -> BullBear:
    """Reason tier; at most 3 grounded points a side."""
    sources = {"SCR": "Financial snapshot (screener.in, from company filings)\n" + snapshot_text(snapshot)}
    for r in delivery:
        sources.setdefault(r.target.source_id, "")
        sources[r.target.source_id] += (f"Management said: \"{r.target.quote}\" | delivered: "
                                        f"{r.actual.value if r.actual.value is not None else 'n/a'} "
                                        f"({r.actual.quarters_in} of {r.actual.quarters_needed} quarters) | "
                                        f"verdict: {VERDICT_WORDS[r.verdict]}\n")
    if business:
        for sid in business.source_ids:
            sources.setdefault(sid, "")
            sources[sid] += f"Business: {business.what_it_does}\n"
        for seg in business.segments:
            for sid in seg.source_ids:
                sources.setdefault(sid, "")
                share = f" ({seg.share_pct:g}% of revenue)" if seg.share_pct is not None else ""
                sources[sid] += f"Segment: {seg.name}{share}\n"
    blocks = "\n\n".join(f"[{sid}]\n{text.strip()}" for sid, text in sources.items())
    reply = llm.complete_json("reason", GROUNDING_RULES, _BULL_BEAR_PROMPT.format(sources=blocks), BullBear,
                              max_tokens=6000)
    for p in reply.bull + reply.bear:
        p.source_ids = _clean(p.source_ids)
    valid = set(sources)
    return BullBear(bull=drop_uncited(reply.bull, valid, key=lambda p: p.source_ids)[:3],
                    bear=drop_uncited(reply.bear, valid, key=lambda p: p.source_ids)[:3])
