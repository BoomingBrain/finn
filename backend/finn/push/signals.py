"""Per-day price metrics: the close-to-close move and volume against its trailing average. The browser applies
the investor's own thresholds to these; this module only measures."""
import math
from datetime import datetime, time

from finn.models import Bar, DayMetric

SETTLED_AFTER = time(16, 0)


def _complete(b: Bar) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in (b.close, b.volume)) and b.close > 0


def daily_metrics(bars: list[Bar], now: datetime, lookback: int = 20) -> list[DayMetric]:
    """One metric per settled session after the first. Incomplete bars and today's bar before 16:00 IST are
    skipped; the volume average uses the `lookback` sessions before each day."""
    usable = [b for b in sorted(bars, key=lambda b: b.date) if _complete(b)]
    if usable and usable[-1].date == now.date() and now.timetz().replace(tzinfo=None) < SETTLED_AFTER:
        usable = usable[:-1]
    out = []
    for i in range(1, len(usable)):
        bar, prev = usable[i], usable[i - 1]
        history = usable[max(0, i - lookback):i]
        avg = sum(b.volume for b in history) / len(history) if len(history) == lookback else 0
        out.append(DayMetric(date=bar.date, close=bar.close, change_pct=round((bar.close / prev.close - 1) * 100, 2),
                             volume_multiple=round(bar.volume / avg, 2) if avg > 0 else None))
    return out
