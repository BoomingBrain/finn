"""Adds what makes a filing useful at a glance: the results card for results statements, a one-line summary
for other critical and notable filings. Routine filings cost nothing: no download, no LLM call."""
import logging
import re
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from finn.llm import LLM, BudgetExceeded
from finn.models import Announcement, Category, EnrichedAnnouncement
from finn.push.classify import tier_for
from finn.push.results import compute_results, extract_results, select_statement_page
from finn.sources.documents import DocText, fetch_pdf, pdf_text

log = logging.getLogger(__name__)

_STATEMENT = re.compile(r"financial results", re.I)
_NOT_STATEMENT = re.compile(r"newspaper|presentation|transcript|intimation|to consider|scheduled", re.I)


class _Summary(BaseModel):
    summary: str


_SUMMARY_SYSTEM = ("You summarise Indian stock-exchange filings for an investor who holds the stock. "
                   "Use only the filing text given.")
_SUMMARY_PROMPT = """Filing subject: {subject}

Filing text (first pages):
{text}

In ONE plain sentence of at most 140 characters, say what this filing tells a shareholder: the concrete fact,
with numbers or names if present. No preamble, no company name at the start, no advice.
Reply with ONLY JSON: {{"summary": "..."}}"""


def clip(text: str, limit: int = 140) -> str:
    """At most `limit` characters, cut at a word boundary with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def is_results_statement(a: Announcement) -> bool:
    """The filing that carries the results statement itself (not the newspaper ad, deck or notice)."""
    return bool(_STATEMENT.search(a.subject)) and not _NOT_STATEMENT.search(a.subject)


def enrich(a: Announcement, category: Category, llm: LLM, sector: str | None = None,
           get_pdf: Callable[[str], Path] = fetch_pdf) -> EnrichedAnnouncement:
    tier = tier_for(category, a.subject)
    out = EnrichedAnnouncement(announcement=a, category=category, tier=tier)
    if tier == "routine" or not a.attachment_url:
        return out
    if category == "results" and not is_results_statement(a):
        return out  # decks, ads and auditor reports fold into the results event (Task 6)
    try:
        path = get_pdf(a.attachment_url)
        doc = DocText(url=a.attachment_url, pages=pdf_text(path))
        if category == "results":
            page = select_statement_page(doc)
            if page is not None:
                out.results = compute_results(extract_results(path, page, llm), sector)
        elif doc.readable:
            text = "\n".join(doc.pages[:3])[:6000]
            reply = llm.complete_json("bulk", _SUMMARY_SYSTEM, _SUMMARY_PROMPT.format(subject=a.subject, text=text),
                                      _Summary, max_tokens=200)
            out.summary = clip(reply.summary) or None
    except BudgetExceeded:
        raise
    except Exception as e:  # a bad PDF or model hiccup degrades this item only
        log.warning("enrich failed for %s %s: %s", a.symbol, a.attachment_url, e)
    return out
