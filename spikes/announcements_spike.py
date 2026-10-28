"""Throwaway spike: can we fetch corporate announcements from NSE (and BSE as fallback)?

Usage: uv run python announcements_spike.py [nse|bse] [OUT_DIR]
Saves raw JSON per symbol into OUT_DIR (default ../backend/tests/fixtures).
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
SYMBOLS = ["INFY", "HDFCBANK", "RELIANCE"]
BSE_CODES = {"INFY": "500209", "HDFCBANK": "500180", "RELIANCE": "500325"}


def nse(out: Path) -> dict:
    end = date.today()
    start = end - timedelta(days=30)
    report = {}
    with httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json,text/html,*/*",
                 "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/"},
        timeout=20, follow_redirects=True, http2=False,
    ) as c:
        warm = c.get("https://www.nseindia.com/")
        report["warmup_status"] = warm.status_code
        report["cookies"] = sorted(c.cookies.keys())
        for sym in SYMBOLS:
            url = ("https://www.nseindia.com/api/corporate-announcements?index=equities"
                   f"&symbol={sym}&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}")
            t = time.time()
            r = c.get(url)
            entry = {"status": r.status_code, "secs": round(time.time() - t, 2)}
            try:
                data = r.json()
                entry["count"] = len(data) if isinstance(data, list) else None
                entry["fields"] = sorted(data[0].keys()) if isinstance(data, list) and data else None
                (out / f"announcements_nse_{sym}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                entry["error"] = f"{type(e).__name__}: {r.text[:200]!r}"
            report[sym] = entry
            time.sleep(0.7)
    return report


def bse(out: Path) -> dict:
    end = date.today()
    start = end - timedelta(days=30)
    report = {}
    with httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                 "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"},
        timeout=20, follow_redirects=True,
    ) as c:
        for sym, code in BSE_CODES.items():
            url = ("https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1"
                   f"&strPrevDate={start:%Y%m%d}&strScrip={code}&strSearch=P&strToDate={end:%Y%m%d}&strType=C&subcategory=-1")
            r = c.get(url)
            entry = {"status": r.status_code}
            try:
                data = r.json()
                rows = data.get("Table", []) if isinstance(data, dict) else []
                entry["count"] = len(rows)
                entry["fields"] = sorted(rows[0].keys()) if rows else None
                (out / f"announcements_bse_{sym}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                entry["error"] = f"{type(e).__name__}: {r.text[:200]!r}"
            report[sym] = entry
            time.sleep(0.7)
    return report


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "nse"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent.parent / "backend/tests/fixtures")
    out.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"nse": nse, "bse": bse}[which](out), indent=1))
