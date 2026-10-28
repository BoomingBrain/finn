"""Cost guards for live research: a per-IP sliding-window limit and the NSE symbol list that decides what is a
real ticker before any fetch or model call happens."""
import csv
import threading
from collections import defaultdict, deque
from functools import cache
from pathlib import Path

from finn.snapshot import SnapshotStore

SYMBOLS_CSV = Path(__file__).parent / "data" / "nse_symbols.csv"


class RateLimiter:
    """At most `per_hour` allowed calls per key in any rolling 3600 s window."""

    def __init__(self, per_hour: int):
        self.per_hour = per_hour
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float) -> bool:
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - 3600:
                hits.popleft()
            if len(hits) >= self.per_hour:
                return False
            hits.append(now)
            return True


@cache
def nse_symbols() -> dict[str, str]:
    """Symbol -> company name, from NSE's EQUITY_L.csv."""
    with open(SYMBOLS_CSV, newline="") as f:
        return {row["symbol"]: row["name"] for row in csv.DictReader(f)}


def write_symbols(store: SnapshotStore) -> int:
    """symbols.json = [{symbol, name, precomputed}], which the browser filters for search. Returns the count."""
    ready = set(store.list_dossiers())
    rows = [{"symbol": s, "name": n, "precomputed": s in ready} for s, n in sorted(nse_symbols().items())]
    store.save_symbols(rows)
    return len(rows)
