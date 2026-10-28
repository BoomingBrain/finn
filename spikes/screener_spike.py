"""Throwaway spike: does a screener.in company page give us the tables and document links without login?

Usage: uv run python screener_spike.py [OUT_DIR] [--burst N]
Saves HTML per symbol, downloads the newest transcript PDF, and optionally fires N quick requests
to see whether rate limiting (429) kicks in.
"""
import json
import sys
import time
from pathlib import Path

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
SYMBOLS = ["PIDILITIND", "HDFCBANK"]
SECTIONS = ["quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios", "shareholding", "documents"]


def table_summary(tree: HTMLParser, section_id: str) -> dict | None:
    sec = tree.css_first(f"section#{section_id}")
    if sec is None:
        return None
    table = sec.css_first("table")
    if table is None:
        return {"present": True, "table": False}
    headers = [th.text(strip=True) for th in table.css("thead th")]
    rows = [tr.css_first("td").text(strip=True) for tr in table.css("tbody tr") if tr.css_first("td")]
    return {"columns": headers[1:], "rows": rows}


def doc_links(tree: HTMLParser) -> dict:
    sec = tree.css_first("section#documents")
    if sec is None:
        return {}
    out = {"annual_reports": [], "transcripts": [], "other_concall_links": []}
    for div in sec.css("div.documents"):
        title = (div.css_first("h3") or div).text(strip=True)
        if "Annual" in title:
            for a in div.css("a"):
                out["annual_reports"].append({"label": a.text(strip=True)[:60], "href": a.attributes.get("href")})
        elif "Concall" in title:
            for li in div.css("li"):
                date_el = li.css_first("div")
                for a in li.css("a"):
                    label = a.text(strip=True)
                    item = {"date": date_el.text(strip=True) if date_el else None, "label": label,
                            "href": a.attributes.get("href")}
                    (out["transcripts"] if label == "Transcript" else out["other_concall_links"]).append(item)
    return out


def main(out: Path, burst: int) -> dict:
    report = {}
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as c:
        for sym in SYMBOLS:
            url = f"https://www.screener.in/company/{sym}/consolidated/"
            r = c.get(url)
            entry = {"url": url, "status": r.status_code, "final_url": str(r.url), "bytes": len(r.content)}
            if r.status_code == 200:
                (out / f"screener_{sym}.html").write_text(r.text)
                tree = HTMLParser(r.text)
                entry["login_wall"] = "Login" in (tree.css_first("title").text() if tree.css_first("title") else "")
                entry["sections"] = {s: table_summary(tree, s) for s in SECTIONS if s != "documents"}
                docs = doc_links(tree)
                entry["docs"] = {k: len(v) for k, v in docs.items()}
                entry["newest_transcripts"] = docs.get("transcripts", [])[:4]
                entry["newest_annual_reports"] = docs.get("annual_reports", [])[:2]
                entry["about"] = (tree.css_first(".company-profile .about p") or tree.css_first(".about p"))
                entry["about"] = entry["about"].text(strip=True)[:200] if entry["about"] else None
            report[sym] = entry
            time.sleep(1)

        # Download the newest PIDILITIND transcript as a fixture
        tr = (report.get("PIDILITIND", {}).get("newest_transcripts") or [None])[0]
        if tr and tr["href"]:
            r = c.get(tr["href"], headers={"User-Agent": UA})
            report["transcript_download"] = {"href": tr["href"], "status": r.status_code,
                                             "content_type": r.headers.get("content-type"), "bytes": len(r.content)}
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                d = tr["date"].replace(" ", "_") if tr["date"] else "latest"
                (out / "transcripts" / f"PIDILITIND_{d}.pdf").write_bytes(r.content)

        if burst:
            statuses = []
            for _ in range(burst):
                statuses.append(c.get("https://www.screener.in/company/INFY/consolidated/").status_code)
            report["burst"] = {"n": burst, "statuses": statuses}
    return report


if __name__ == "__main__":
    argv = sys.argv[1:]
    burst = 0
    if "--burst" in argv:
        i = argv.index("--burst")
        burst = int(argv[i + 1])
        del argv[i:i + 2]
    out = Path(argv[0] if argv else Path(__file__).resolve().parent.parent / "backend/tests/fixtures")
    (out / "transcripts").mkdir(parents=True, exist_ok=True)
    print(json.dumps(main(out, burst), indent=1, default=str))
