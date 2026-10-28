"""Throwaway spike: do real results PDFs (linked from NSE announcements) have a usable text layer,
and where are the quarter / half-year / year columns?

Usage: uv run python results_pdf_spike.py [OUT_DIR]
Reads the NSE announcement fixtures, downloads the results attachment for INFY and HDFCBANK,
and prints per-page diagnostics for the pages that look like the results statement.
"""
import json
import re
import sys
from pathlib import Path

import httpx
import pymupdf

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
TARGETS = {"INFY": "INFY_q2fy27.pdf", "HDFCBANK": "HDFCBANK_q2fy27.pdf"}
STATEMENT_HINTS = re.compile(r"(revenue from operations|interest earned|profit before tax|net profit)", re.I)
UNIT_HINTS = re.compile(r"(in\s+(?:₹|rs\.?|inr)?\s*(?:crore|lakh|million|thousand)s?|₹\s*(?:in\s+)?(?:crore|lakh)s?)", re.I)
PERIOD_HINTS = re.compile(r"(quarter ended|three months ended|half[- ]year ended|six months ended|year ended)", re.I)


def results_attachment(fixtures: Path, sym: str) -> str:
    rows = json.loads((fixtures / f"announcements_nse_{sym}.json").read_text())
    for r in rows:
        if r["desc"] == "Outcome of Board Meeting" and "result" in (r["attchmntText"] or "").lower():
            return r["attchmntFile"]
    raise SystemExit(f"no results filing for {sym}")


def main(fixtures: Path) -> dict:
    out = fixtures / "results"
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    with httpx.Client(headers={"User-Agent": UA, "Referer": "https://www.nseindia.com/"}, timeout=60,
                      follow_redirects=True) as c:
        for sym, fname in TARGETS.items():
            url = results_attachment(fixtures, sym)
            r = c.get(url)
            entry = {"url": url, "status": r.status_code, "bytes": len(r.content),
                     "is_pdf": r.content[:4] == b"%PDF"}
            if not entry["is_pdf"]:
                report[sym] = entry
                continue
            (out / fname).write_bytes(r.content)
            doc = pymupdf.open(stream=r.content, filetype="pdf")
            entry["pages"] = doc.page_count
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text()
                if STATEMENT_HINTS.search(text):
                    pages.append({
                        "page": i + 1,
                        "chars": len(text.strip()),
                        "units": sorted({m.group(0).strip() for m in UNIT_HINTS.finditer(text)})[:4],
                        "periods": sorted({m.group(0).lower() for m in PERIOD_HINTS.finditer(text)}),
                        "consolidated": "consolidated" in text.lower(),
                    })
            entry["text_layer_chars_total"] = sum(len(p.get_text().strip()) for p in doc)
            entry["statement_pages"] = pages[:12]
            report[sym] = entry
    return report


if __name__ == "__main__":
    fixtures = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "backend/tests/fixtures")
    print(json.dumps(main(fixtures), indent=1, ensure_ascii=False))
