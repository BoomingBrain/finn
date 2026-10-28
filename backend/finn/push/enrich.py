"""Adds what makes a filing useful at a glance: the results card for results statements, a one-line summary
for other critical and notable filings. Routine filings cost nothing: no download, no LLM call."""
import logging
import re
from pathlib import Path
from typing import Callable

from typing import Literal

from pydantic import BaseModel

from finn.llm import LLM, BudgetExceeded
from finn.models import Announcement, Category, EnrichedAnnouncement, PersonProfile
from finn.push.classify import tier_for
from finn.push.results import compute_results, extract_results, select_statement_page
from finn.sources.documents import DocText, fetch_pdf, pdf_text, render_page_png

log = logging.getLogger(__name__)

_NOT_STATEMENT = re.compile(r"newspaper|presentation|transcript|recording|intimation|to consider|scheduled|"
                            r"to announce", re.I)
_NO_PROFILE = re.compile(r"^\W*(not applicable|n\.?a\.?|nil|none|-+)\W*$", re.I)


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


class _Profile(BaseModel):
    found: bool
    name: str | None = None
    role: str | None = None
    change: Literal["appointed", "resigned", "retired"] | None = None
    effective_date: str | None = None
    background: str | None = None
    prior_roles: list[str] = []


_PROFILE_SYSTEM = ("You read Indian stock-exchange filings about changes in a company's management. "
                   "Use only what the filing says; never add outside knowledge about the person.")
_PROFILE_PROMPT = """Identify the person this filing is about: the person joining if anyone joins, otherwise the
person leaving. Reply with ONLY JSON:
{"found": true|false, "name": "...", "role": "the position, e.g. Chief Financial Officer",
 "change": "appointed|resigned|retired", "effective_date": "as written, or null",
 "background": "1-2 sentences from the filing's brief profile: education, prior roles, years of experience (max 280 characters), or null if the filing has no profile of the person",
 "prior_roles": ["up to 3 earlier roles named in the profile"]}
Set "found": false only if no specific person is named."""


def extract_profile(doc: DocText, llm: LLM, images: list[bytes] = ()) -> PersonProfile | None:
    """The appointee's (or leaver's) profile from the filing; None if no person is named. An empty background
    means the filing names the person but has no profile section ("No profile in filing" in the app)."""
    user = _PROFILE_PROMPT + ("" if images else "\n\nFiling text:\n" + "\n".join(doc.pages[:4])[:8000])
    reply = llm.complete_json("vision" if images else "bulk", _PROFILE_SYSTEM, user, _Profile, images=list(images),
                              max_tokens=500)
    if not reply.found or not reply.name or not reply.change:
        return None
    return PersonProfile(name=reply.name.strip(), role=(reply.role or "").strip(), change=reply.change,
                         effective_date=reply.effective_date, background=clip(clean_background(reply.background), 280),
                         prior_roles=reply.prior_roles[:3])


def clip(text: str, limit: int = 140) -> str:
    """At most `limit` characters, cut at a word boundary with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def is_results_statement(a: Announcement) -> bool:
    """Could carry the results statement itself (not an ad, deck, transcript or notice). The PDF decides: only a
    page with income and PBT rows gets read (e.g. Persistent's "Outcome of the Board Meeting" holds its results)."""
    return not _NOT_STATEMENT.search(a.subject)


def clean_background(text: str | None) -> str:
    """Resignation filings often say "Brief profile: Not Applicable"; that is no profile."""
    text = (text or "").strip()
    return "" if _NO_PROFILE.match(text) else text


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
        elif category == "management_change":
            images = [] if doc.readable else [render_page_png(path, i) for i in range(min(2, len(doc.pages)))]
            out.profile = extract_profile(doc, llm, images)  # scanned filings are read as images
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
