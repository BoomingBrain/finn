"""End-of-day prices from Yahoo Finance (.NS). Today's bar is dropped before 16:00 IST: during market hours
yfinance returns a partial bar (Task 0: INFY showed -4.8% on a third of normal volume mid-session)."""
import logging
from datetime import datetime, time

import pandas as pd
import yfinance as yf

from finn.models import IST, Bar

log = logging.getLogger(__name__)
SETTLED_AFTER = time(16, 0)


def fetch_eod(symbols: list[str], days: int = 120, now: datetime | None = None) -> dict[str, list[Bar]]:
    """Bars per symbol, oldest first. Symbols that fail are omitted."""
    now = now or datetime.now(IST)
    tickers = [f"{s}.NS" for s in symbols]
    df = yf.download(tickers, period=f"{days}d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
    out: dict[str, list[Bar]] = {}
    for symbol, ticker in zip(symbols, tickers):
        try:
            frame = df[ticker] if isinstance(df.columns, pd.MultiIndex) else df
            frame = frame[["Close", "Volume"]].dropna()
        except KeyError:
            log.warning("no prices for %s", symbol)
            continue
        bars = [Bar(date=idx.date(), close=float(row.Close), volume=float(row.Volume)) for idx, row in frame.iterrows()]
        if bars and bars[-1].date == now.date() and now.timetz().replace(tzinfo=None) < SETTLED_AFTER:
            bars = bars[:-1]  # partial session
        if bars:
            out[symbol] = bars
    return out
