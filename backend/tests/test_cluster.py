from datetime import date, datetime, timedelta

from finn.models import IST, Announcement, Bar, EnrichedAnnouncement, MetricRow, PersonProfile, ResultsCard
from finn.push.cluster import cluster_events

CARD = ResultsCard(status="ok", layout="corporate", basis="consolidated", period_end=date(2026, 9, 30),
                   metrics={"Revenue": MetricRow(current=1, prev_q=1, year_ago=1, qoq_pct=0, yoy_pct=0)})


def item(subject, when, symbol="INFY", category="results", tier="critical", results=None, profile=None, summary=None):
    filed = datetime.fromisoformat(when).replace(tzinfo=IST)
    a = Announcement(id=Announcement.make_id(symbol, filed, subject), symbol=symbol, company=symbol, filed_at=filed,
                     subject=subject, body="", attachment_url=f"https://x/{subject}.pdf", raw_category=None, source="nse")
    return EnrichedAnnouncement(announcement=a, category=category, tier=tier, results=results, profile=profile,
                                summary=summary)


def bars(start: date, closes: list[float], volumes: list[float] | None = None) -> list[Bar]:
    """Consecutive weekday bars."""
    out, d = [], start
    for i, close in enumerate(closes):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(Bar(date=d, close=close, volume=(volumes or [1000] * len(closes))[i]))
        d += timedelta(days=1)
    return out


def test_results_day_folds_into_one_event():
    items = [item("Board meeting outcome", "2026-10-23T16:05"),
             item("Financial results", "2026-10-23T16:10", results=CARD),
             item("Investor presentation", "2026-10-23T16:30"),
             item("Newspaper ad", "2026-10-24T09:00")]
    events = cluster_events(items, {})
    assert len(events) == 1
    e = events[0]
    assert [d.title for d in e.documents] == ["Board meeting outcome", "Financial results", "Investor presentation",
                                              "Newspaper ad"]
    assert e.results == CARD and e.headline == "Financial results"
    assert e.id == items[0].announcement.id
    assert (e.first_at.hour, e.last_at.day) == (16, 24)


def test_next_evening_newspaper_ad_still_folds_in():
    # Real INFY Q2 FY27: results 23 Oct 16:08, newspaper ad 24 Oct 19:43 (27.6 h later)
    items = [item("Financial results", "2026-10-23T16:08", results=CARD), item("Newspaper ad", "2026-10-24T19:43")]
    assert len(cluster_events(items, {})) == 1


def test_different_categories_same_day_stay_separate():
    items = [item("Financial results", "2026-10-23T16:10", results=CARD),
             item("CFO resigns", "2026-10-23T17:00", category="management_change")]
    assert len(cluster_events(items, {})) == 2


def test_different_companies_stay_separate():
    items = [item("Financial results", "2026-10-23T16:10", symbol="INFY"),
             item("Financial results", "2026-10-23T16:20", symbol="TCS")]
    assert len(cluster_events(items, {})) == 2


def test_more_than_36h_apart_stay_separate():
    items = [item("Financial results", "2026-10-19T15:40"), item("Financial results", "2026-10-23T16:10")]
    assert len(cluster_events(items, {})) == 2


def test_event_tier_is_max_member_tier():
    items = [item("Results date notice", "2026-10-23T09:00", tier="routine"),
             item("Financial results", "2026-10-23T16:10", results=CARD)]
    e = cluster_events(items, {})[0]
    assert e.tier == "critical" and e.headline == "Financial results"


def test_profile_member_heads_management_change():
    p = PersonProfile(name="A B", role="CFO", change="appointed", effective_date=None, background="x", prior_roles=[])
    items = [item("Change in management", "2026-10-01T18:00", category="management_change"),
             item("Appointment of CFO", "2026-10-01T18:30", category="management_change", profile=p)]
    e = cluster_events(items, {})[0]
    assert e.profile == p and e.headline == "Appointment of CFO"


def test_events_newest_first():
    items = [item("Old", "2026-10-01T10:00", category="dividend", tier="notable"),
             item("New", "2026-10-20T10:00", category="dividend", tier="notable")]
    assert [e.headline for e in cluster_events(items, {})] == ["New", "Old"]


def test_price_change_attached():
    # Thu 22 Oct close 100, Fri 23 Oct close 104; filed Fri 10:00 (market open) -> that day's move
    prices = {"INFY": bars(date(2026, 10, 22), [100, 104])}
    e = cluster_events([item("Financial results", "2026-10-23T10:00", results=CARD)], prices)[0]
    assert e.price_change_pct == 4.0 and e.price_date == date(2026, 10, 23)


def test_after_close_uses_next_trading_day():
    # Filed Fri 23 Oct 16:08, after the 15:30 close -> reaction is Mon 26 Oct
    prices = {"INFY": bars(date(2026, 10, 22), [100, 104, 99.84])}
    e = cluster_events([item("Financial results", "2026-10-23T16:08", results=CARD)], prices)[0]
    assert e.price_date == date(2026, 10, 26) and e.price_change_pct == -4.0


def test_reaction_not_yet_traded_gives_none():
    prices = {"INFY": bars(date(2026, 10, 22), [100, 104])}  # no bar after Fri yet
    e = cluster_events([item("Financial results", "2026-10-23T16:08", results=CARD)], prices)[0]
    assert e.price_change_pct is None and e.price_date is None


def test_no_bars_gives_none():
    e = cluster_events([item("Financial results", "2026-10-23T10:00", results=CARD)], {})[0]
    assert e.price_change_pct is None and e.volume_multiple is None


def test_volume_multiple_against_20_day_average():
    closes = [100.0] * 21
    volumes = [1000.0] * 20 + [2500.0]
    prices = {"INFY": bars(date(2026, 9, 24), closes, volumes)}
    reaction_day = prices["INFY"][-1].date
    e = cluster_events([item("Financial results", f"{reaction_day}T11:00", results=CARD)], prices)[0]
    assert e.volume_multiple == 2.5


def test_short_history_gives_no_volume_multiple():
    prices = {"INFY": bars(date(2026, 10, 19), [100, 101, 102], [1000, 1000, 3000])}
    e = cluster_events([item("Financial results", f"{prices['INFY'][-1].date}T11:00", results=CARD)], prices)[0]
    assert e.volume_multiple is None and e.price_change_pct is not None
