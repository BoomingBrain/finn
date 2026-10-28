"""Corporate announcements from NSE (Task 0: NSE works locally and from cloud runners; BSE's API is blocked).
Field mapping is in docs/spikes.md: subject = attchmntText, raw_category = desc, filed_at = sort_date (IST)."""
import logging
import re
import time
from datetime import date, datetime

import httpx
from pydantic import BaseModel

from finn.models import Announcement
from finn.portfolio import Holding

log = logging.getLogger(__name__)

NSE_HOME = "https://www.nseindia.com/"
NSE_API = "https://www.nseindia.com/api/corporate-announcements"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")


class FetchResult(BaseModel):
    items: list[Announcement]
    failed: list[str]


def parse_nse(rows: list[dict]) -> list[Announcement]:
    out: dict[str, Announcement] = {}
    for r in rows:
        if not r.get("sort_date") or not r.get("symbol"):
            log.warning("skipping NSE row without sort_date/symbol: %s", r.get("seq_id"))
            continue
        filed = datetime.strptime(r["sort_date"], "%Y-%m-%d %H:%M:%S")  # IST, attached by the model
        subject = re.sub(r"\s+", " ", (r.get("attchmntText") or r.get("desc") or "")).strip()
        attachment = (r.get("attchmntFile") or "").strip()
        a = Announcement(
            id=Announcement.make_id(r["symbol"], filed, subject), symbol=r["symbol"], company=r.get("sm_name") or r["symbol"],
            filed_at=filed, subject=subject, body="", attachment_url=attachment if attachment.startswith("http") else None,
            raw_category=r.get("desc"), source="nse")
        out[a.id] = a
    return list(out.values())


class NSEClient:
    def __init__(self, timeout: float = 20, spacing: float = 0.5):
        self.http = httpx.Client(timeout=timeout, follow_redirects=True, headers={
            "User-Agent": UA, "Accept": "application/json,text/html,*/*", "Accept-Language": "en-US,en;q=0.9",
            "Referer": NSE_HOME})
        self.spacing = spacing
        self._warmed = False

    def _warm(self) -> None:
        try:  # sets cookies; from cloud IPs the homepage may 403 while the API still answers (Task 0)
            self.http.get(NSE_HOME)
        except httpx.HTTPError as e:
            log.info("NSE warm-up failed: %s", e)
        self._warmed = True

    def fetch(self, symbol: str, start: date, end: date) -> list[Announcement]:
        if not self._warmed:
            self._warm()
        params = {"index": "equities", "symbol": symbol, "from_date": f"{start:%d-%m-%Y}", "to_date": f"{end:%d-%m-%Y}"}
        r = self.http.get(NSE_API, params=params)
        if r.status_code in (401, 403):
            self._warm()
            r = self.http.get(NSE_API, params=params)
        r.raise_for_status()
        data = r.json()
        return parse_nse(data if isinstance(data, list) else data.get("data", []))


def fetch_announcements(holdings: list[Holding], start: date, end: date, client: NSEClient | None = None) -> FetchResult:
    client = client or NSEClient()
    items: list[Announcement] = []
    failed: list[str] = []
    for i, h in enumerate(holdings):
        if i:
            time.sleep(client.spacing)
        try:
            items.extend(client.fetch(h.symbol, start, end))
        except Exception as e:  # one bad symbol never drops the rest
            log.warning("NSE fetch failed for %s: %s", h.symbol, e)
            failed.append(h.symbol)
    return FetchResult(items=items, failed=failed)
