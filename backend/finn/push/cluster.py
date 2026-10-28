"""Folds related filings into one event: same company, same category, filed within 36 hours of the event's
first filing (results day: board outcome, statement, deck, next-day newspaper ad). Attaches the market's reaction:
the close-to-close move and volume multiple on the trading day the headline filing could first be traded on."""
from datetime import datetime, time, timedelta

from finn.models import Bar, DocRef, EnrichedAnnouncement, Event
from finn.push.events import headline

WINDOW = timedelta(hours=36)  # INFY's Q2 FY27 newspaper ad came 27.6 h after its results
MARKET_CLOSE = time(15, 30)
VOLUME_LOOKBACK = 20
TIER_RANK = {"critical": 2, "notable": 1, "routine": 0}


def _lead(members: list[EnrichedAnnouncement]) -> EnrichedAnnouncement:
    """Headline member: has results > has profile > highest tier > earliest."""
    return min(members, key=lambda m: (m.results is None, m.profile is None, -TIER_RANK[m.tier],
                                       m.announcement.filed_at))


def _reaction(bars: list[Bar], filed_at: datetime) -> tuple[float | None, float | None, object]:
    """(change %, volume multiple, trading date) for the first session that could react to a filing."""
    filed_day = filed_at.date()
    after_close = filed_at.timetz().replace(tzinfo=None) >= MARKET_CLOSE
    idx = next((i for i, b in enumerate(bars) if b.date > filed_day or (b.date == filed_day and not after_close)), None)
    if idx is None or idx == 0:
        return None, None, None
    bar, prev = bars[idx], bars[idx - 1]
    change = round((bar.close / prev.close - 1) * 100, 1) if prev.close else None
    history = bars[max(0, idx - VOLUME_LOOKBACK):idx]
    avg = sum(b.volume for b in history) / len(history) if len(history) == VOLUME_LOOKBACK else 0
    multiple = round(bar.volume / avg, 1) if avg else None
    return change, multiple, bar.date


def _event(members: list[EnrichedAnnouncement], bars: list[Bar]) -> Event:
    lead = _lead(members)
    a = lead.announcement
    change, multiple, day = _reaction(bars, a.filed_at)
    docs = [DocRef(title=headline(m.announcement.subject, m.announcement.raw_category), url=m.announcement.attachment_url,
                   filed_at=m.announcement.filed_at) for m in members]
    return Event(
        id=members[0].announcement.id, symbol=a.symbol, company=a.company, category=lead.category,
        tier=max((m.tier for m in members), key=TIER_RANK.get), first_at=members[0].announcement.filed_at,
        last_at=members[-1].announcement.filed_at, headline=headline(a.subject, a.raw_category),
        summary=lead.summary or next((m.summary for m in members if m.summary), None),
        results=next((m.results for m in members if m.results), None),
        profile=next((m.profile for m in members if m.profile), None),
        documents=docs, price_change_pct=change, volume_multiple=multiple, price_date=day)


def cluster_events(items: list[EnrichedAnnouncement], prices: dict[str, list[Bar]]) -> list[Event]:
    clusters: list[list[EnrichedAnnouncement]] = []
    open_by_key: dict[tuple[str, str], list[EnrichedAnnouncement]] = {}
    for item in sorted(items, key=lambda m: m.announcement.filed_at):
        key = (item.announcement.symbol, item.category)
        current = open_by_key.get(key)
        if current and item.announcement.filed_at - current[0].announcement.filed_at <= WINDOW:
            current.append(item)
        else:
            open_by_key[key] = [item]
            clusters.append(open_by_key[key])
    events = [_event(c, sorted(prices.get(c[0].announcement.symbol, []), key=lambda b: b.date)) for c in clusters]
    return sorted(events, key=lambda e: e.last_at, reverse=True)
