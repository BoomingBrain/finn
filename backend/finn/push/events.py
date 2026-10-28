"""Turns enriched announcements into the events the Brief shows. Task 6 replaces to_event with clustering."""
import re

from finn.models import DocRef, EnrichedAnnouncement, Event

_BOILERPLATE = re.compile(r"^.*?\bhas (informed|submitted to) the exchange\b(\s+(that|about|regarding))?[\s,:-]*",
                          re.I)


def headline(subject: str, fallback: str | None = None) -> str:
    """'Infosys Limited has informed the Exchange regarding 'X'.' -> 'X'."""
    text = _BOILERPLATE.sub("", subject).strip().strip("'\"‘’“” .").strip()
    text = text or (fallback or subject)
    return text[:1].upper() + text[1:]


def to_event(e: EnrichedAnnouncement) -> Event:
    a = e.announcement
    title = headline(a.subject, a.raw_category)
    return Event(id=a.id, symbol=a.symbol, company=a.company, category=e.category, tier=e.tier,
                 first_at=a.filed_at, last_at=a.filed_at, headline=title, summary=e.summary, results=e.results,
                 profile=e.profile, documents=[DocRef(title=title, url=a.attachment_url, filed_at=a.filed_at)],
                 price_change_pct=None, volume_multiple=None)
