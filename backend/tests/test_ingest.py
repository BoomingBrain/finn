from datetime import datetime

from finn.ingest import ingest
from finn.llm import LLM
from finn.models import IST, Announcement, EnrichedAnnouncement
from finn.snapshot import SnapshotStore
from finn.sources.announcements import FetchResult
from tests.fakes import FakeCompleter

NOW = datetime(2026, 10, 28, 18, 0, tzinfo=IST)


def _ann(subject):
    filed = datetime(2026, 10, 20, 12, 0, tzinfo=IST)
    return Announcement(id=Announcement.make_id("INFY", filed, subject), symbol="INFY", company="Infosys",
                        filed_at=filed, subject=subject, body="", attachment_url=None, raw_category="General Updates",
                        source="nse")


def test_reprocess_keeps_stored_category(tmp_path):
    # An unruled filing the LLM once labelled "M&A": re-enriching must not send it back to the LLM to re-classify
    a = _ann("Something no rule matches")
    store = SnapshotStore(tmp_path)
    fetch = lambda holdings, start, end: FetchResult(items=[a], failed=[])
    enrich = lambda ann, category, llm, sector=None: EnrichedAnnouncement(announcement=ann, category=category, tier="critical")
    llm_first = LLM(tmp_path / "a.sqlite", completer=FakeCompleter(['{"labels": [{"i": 0, "category": "M&A"}]}']))
    ingest(["INFY"], 30, store, llm_first, NOW, fetch=fetch, enrich_fn=enrich, fetch_prices=lambda s, now: {})

    fake = FakeCompleter(['{"labels": [{"i": 0, "category": "unclassified"}]}'])
    report = ingest(["INFY"], 30, store, LLM(tmp_path / "b.sqlite", completer=fake), NOW, fetch=fetch, enrich_fn=enrich,
                    fetch_prices=lambda s, now: {}, reprocess=frozenset({"M&A"}))
    assert report.new == 1
    assert fake.calls == []
    assert store.load_push().announcements[0].category == "M&A"


def test_rerun_without_reprocess_does_nothing_new(tmp_path):
    a = _ann("Something no rule matches")
    store = SnapshotStore(tmp_path)
    fetch = lambda holdings, start, end: FetchResult(items=[a], failed=[])
    enrich = lambda ann, category, llm, sector=None: EnrichedAnnouncement(announcement=ann, category=category, tier="routine")
    llm = LLM(tmp_path / "a.sqlite", completer=FakeCompleter(['{"labels": [{"i": 0, "category": "unclassified"}]}']))
    ingest(["INFY"], 30, store, llm, NOW, fetch=fetch, enrich_fn=enrich, fetch_prices=lambda s, now: {})
    assert ingest(["INFY"], 30, store, llm, NOW, fetch=fetch, enrich_fn=enrich, fetch_prices=lambda s, now: {}).new == 0
