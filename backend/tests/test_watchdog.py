from datetime import datetime, timedelta, timezone

from finn.models import IST
from finn.watchdog import overdue

THU_11 = datetime(2026, 10, 29, 11, 0, tzinfo=IST)  # a market day, mid-morning
SAT_11 = datetime(2026, 10, 31, 11, 0, tzinfo=IST)


def test_ingest_overdue_after_two_and_a_half_hours_in_market_hours():
    assert not overdue("ingest", THU_11 - timedelta(hours=2), THU_11)
    assert overdue("ingest", THU_11 - timedelta(hours=3), THU_11)


def test_ingest_allows_a_long_gap_outside_market_hours():
    assert not overdue("ingest", SAT_11 - timedelta(hours=10), SAT_11)
    assert overdue("ingest", SAT_11 - timedelta(hours=15), SAT_11)


def test_daily_jobs_overdue_after_26_hours():
    assert not overdue("dossiers", THU_11 - timedelta(hours=25), THU_11)
    assert overdue("dossiers", THU_11 - timedelta(hours=27), THU_11)
    assert overdue("prebuild", THU_11 - timedelta(hours=27), THU_11)


def test_never_run_is_overdue_and_times_compare_across_zones():
    assert overdue("ingest", None, THU_11)
    utc_recent = (THU_11 - timedelta(minutes=30)).astimezone(timezone.utc)
    assert not overdue("ingest", utc_recent, THU_11)
