from datetime import date, datetime, timedelta

from finn.models import IST, Bar
from finn.push.signals import daily_metrics

EVENING = datetime(2026, 12, 31, 18, 0, tzinfo=IST)


def weekday_bars(closes, volumes=None, start=date(2026, 9, 1)):
    out, d = [], start
    for i, close in enumerate(closes):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(Bar(date=d, close=close, volume=(volumes or [1000] * len(closes))[i]))
        d += timedelta(days=1)
    return out


def test_volume_multiple():
    m = daily_metrics(weekday_bars([100] * 21, [1000] * 20 + [2500]), now=EVENING)
    assert m[-1].volume_multiple == 2.5


def test_change_pct_down():
    m = daily_metrics(weekday_bars([100, 94]), now=EVENING)
    assert m[-1].change_pct == -6.0
    assert len(m) == 1  # the first bar has no previous close


def test_short_history_volume_none():
    m = daily_metrics(weekday_bars([100] * 10, [1000] * 9 + [5000]), now=EVENING)
    assert m[-1].volume_multiple is None
    assert m[-1].change_pct == 0.0


def test_zero_avg_volume():
    m = daily_metrics(weekday_bars([100] * 21, [0] * 20 + [500]), now=EVENING)
    assert m[-1].volume_multiple is None


def test_trailing_nan_row_skipped():
    bars = weekday_bars([100, 101, 102])
    bars.append(Bar(date=bars[-1].date + timedelta(days=1), close=float("nan"), volume=float("nan")))
    m = daily_metrics(bars, now=EVENING)
    assert m[-1].date == bars[2].date and m[-1].change_pct == 0.99  # 101 -> 102


def test_today_dropped_before_close():
    bars = weekday_bars([100, 101, 95], start=date(2026, 10, 26))  # Mon 26, Tue 27, Wed 28 Oct
    m = daily_metrics(bars, now=datetime(2026, 10, 28, 11, 0, tzinfo=IST))
    assert m[-1].date == date(2026, 10, 27)
    assert daily_metrics(bars, now=datetime(2026, 10, 28, 16, 30, tzinfo=IST))[-1].date == date(2026, 10, 28)
