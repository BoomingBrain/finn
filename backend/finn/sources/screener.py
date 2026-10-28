"""screener.in company pages: multi-year financial tables (standardised from the company's own filings) plus
links to annual reports and concall transcripts. Structure notes are in docs/spikes.md."""
import re
import time
from datetime import date, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel
from selectolax.lexbor import LexborHTMLParser

from finn.snapshot import REPO_ROOT

BASE = "https://www.screener.in"
DEFAULT_CACHE = REPO_ROOT / "backend" / ".cache" / "screener"
CACHE_SECONDS = 24 * 3600
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                                      "Dec"], start=1)}


class CompanyNotFound(Exception):
    pass


class SourceUnreachable(Exception):
    pass


class Table(BaseModel):
    columns: list[str]
    rows: dict[str, list[float | None]]

    def row(self, *names: str) -> list[float | None] | None:
        """The first row present among `names` (aliases), else None."""
        return next((self.rows[n] for n in names if n in self.rows), None)


class DocLink(BaseModel):
    label: str
    date: date | None
    url: str


class CompanyData(BaseModel):
    symbol: str
    name: str
    about: str
    basis: str  # "consolidated" | "standalone"
    quarters: Table
    pnl: Table
    balance_sheet: Table
    cash_flow: Table
    ratios: Table
    annual_reports: list[DocLink]
    transcripts: list[DocLink]  # newest first
    result_pdfs: dict[str, str] = {}  # quarter label -> screener "Raw PDF" link (redirects to the BSE filing)


def _number(text: str) -> float | None:
    text = text.replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _table(tree: LexborHTMLParser, section_id: str) -> tuple[Table, dict[str, str]]:
    """The section's table, plus any per-column links in a "Raw PDF" row."""
    table = tree.css_first(f"section#{section_id} table")
    if table is None:
        return Table(columns=[], rows={}), {}
    columns = [th.text(strip=True) for th in table.css("thead th")][1:]
    rows: dict[str, list[float | None]] = {}
    links: dict[str, str] = {}
    for tr in table.css("tbody tr"):
        cells = tr.css("td")
        if not cells:
            continue
        name = re.sub(r"\s*\+$", "", cells[0].text(strip=True))
        if name == "Raw PDF":
            for col, td in zip(columns, cells[1:]):
                a = td.css_first("a")
                if a and a.attributes.get("href"):
                    links[col] = BASE + a.attributes["href"] if a.attributes["href"].startswith("/") else a.attributes["href"]
            continue
        rows[name] = [_number(td.text(strip=True)) for td in cells[1:]]
    return Table(columns=columns, rows=rows), links


def _month_year(text: str) -> date | None:
    m = re.search(r"([A-Z][a-z]{2})\w*\s+(\d{4})", text)
    return date(int(m.group(2)), MONTHS[m.group(1)], 1) if m and m.group(1) in MONTHS else None


def _documents(tree: LexborHTMLParser) -> tuple[list[DocLink], list[DocLink]]:
    annual, transcripts = [], []
    for block in tree.css("section#documents div.documents"):
        heading = (block.css_first("h3").text(strip=True) if block.css_first("h3") else "").lower()
        if heading.startswith("annual"):
            for a in block.css("li a"):
                label = a.text(strip=True)
                year = re.search(r"(\d{4})", label)
                if a.attributes.get("href"):
                    annual.append(DocLink(label=label, date=date(int(year.group(1)), 3, 31) if year else None,
                                          url=a.attributes["href"]))
        elif heading.startswith("concall"):
            for li in block.css("li"):
                when = li.css_first("div")
                for a in li.css("a"):
                    if a.text(strip=True) == "Transcript" and a.attributes.get("href"):
                        transcripts.append(DocLink(label=f"Transcript {when.text(strip=True) if when else ''}".strip(),
                                                   date=_month_year(when.text(strip=True)) if when else None,
                                                   url=a.attributes["href"]))
    transcripts.sort(key=lambda d: d.date or date.min, reverse=True)
    return annual, transcripts


def parse_company(html: str, symbol: str, basis: str) -> CompanyData:
    tree = LexborHTMLParser(html)
    quarters, pdfs = _table(tree, "quarters")
    about = tree.css_first(".company-profile .about") or tree.css_first(".about")
    annual, transcripts = _documents(tree)
    return CompanyData(
        symbol=symbol, name=tree.css_first("h1").text(strip=True) if tree.css_first("h1") else symbol,
        about=about.text(strip=True) if about else "", basis=basis, quarters=quarters,
        pnl=_table(tree, "profit-loss")[0], balance_sheet=_table(tree, "balance-sheet")[0],
        cash_flow=_table(tree, "cash-flow")[0], ratios=_table(tree, "ratios")[0],
        annual_reports=annual, transcripts=transcripts, result_pdfs=pdfs)


def _get(url: str) -> str:
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    except httpx.HTTPError as e:
        raise SourceUnreachable(f"{url}: {type(e).__name__}") from e
    if r.status_code == 404:
        raise CompanyNotFound(url)
    if r.status_code != 200:
        raise SourceUnreachable(f"{url}: HTTP {r.status_code}")
    return r.text


def fetch_company(symbol: str, cache_dir: Path = DEFAULT_CACHE) -> CompanyData:
    """Consolidated figures, or standalone when the company has no consolidated quarters. Cached for 24 h."""
    symbol = symbol.upper()
    cache_dir.mkdir(parents=True, exist_ok=True)
    for basis, path in [("consolidated", f"/company/{symbol}/consolidated/"), ("standalone", f"/company/{symbol}/")]:
        cached = cache_dir / f"{symbol}.{basis}.html"
        if cached.exists() and time.time() - cached.stat().st_mtime < CACHE_SECONDS:
            html = cached.read_text()
        else:
            html = _get(BASE + path)
            cached.write_text(html)
        company = parse_company(html, symbol, basis)
        if company.quarters.columns:
            return company
    raise CompanyNotFound(f"{symbol}: no financial tables on screener.in")
