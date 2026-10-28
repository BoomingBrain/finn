"""Promised vs Delivered. The model only copies explicit numeric targets out of concall transcripts; code works out
what was delivered from screener's reported quarters and decides the verdict. The model then writes one line
explaining a verdict it cannot change."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Literal

from pydantic import BaseModel

from finn.llm import LLM, BudgetExceeded, LLMError
from finn.sources.documents import DocText
from finn.sources.screener import Table

log = logging.getLogger(__name__)

Metric = Literal["revenue_growth_yoy", "revenue", "ebitda_margin", "pat_growth_yoy", "pat", "other"]
Comparison = Literal["gte", "lte", "between", "approx"]
Verdict = Literal["met", "partly", "missed", "pending", "not_checkable"]

UNIT_FOR = {"revenue_growth_yoy": "pct", "pat_growth_yoy": "pct", "ebitda_margin": "pct", "revenue": "cr",
            "pat": "cr"}
REVENUE, OP_PROFIT, PAT = ("Sales", "Revenue"), ("Operating Profit",), ("Net Profit",)
SYMBOL = {"gte": "≥", "lte": "≤", "between": "between", "approx": "≈"}


class GuidanceTarget(BaseModel):
    metric: Metric
    raw_metric: str
    comparison: Comparison
    value: float
    value_high: float | None = None
    unit: Literal["pct", "cr"]
    period: str  # FY27, Q3FY27, H2FY27
    quote: str
    source_id: str  # T:{YYYY-MM-DD}:p{n}
    said_on: date


class Actual(BaseModel):
    value: float | None
    quarters_in: int
    quarters_needed: int  # 0 when the target can't be checked from reported numbers


class DeliveryRow(BaseModel):
    target: GuidanceTarget
    actual: Actual
    verdict: Verdict
    explanation: str


# ---- periods ---------------------------------------------------------------------------------------------------

def resolve_period(period: str) -> list[str] | None:
    """Screener quarter labels for an Indian fiscal period: FY27 = Jun 2026, Sep 2026, Dec 2026, Mar 2027."""
    p = re.sub(r"[\s\-']", "", period.upper())
    m = re.fullmatch(r"(?:(Q[1-4]|[1-4]Q|H[12]|[12]H))?FY(\d{2}|\d{4})", p)
    if not m:
        return None
    fy = int(m.group(2)) % 100 + 2000
    quarters = [f"Jun {fy - 1}", f"Sep {fy - 1}", f"Dec {fy - 1}", f"Mar {fy}"]
    part = m.group(1)
    if not part:
        return quarters
    n = int(re.sub(r"\D", "", part))
    return [quarters[n - 1]] if "Q" in part else quarters[(n - 1) * 2:n * 2]


def _year_earlier(label: str) -> str:
    month, year = label.split()
    return f"{month} {int(year) - 1}"


# ---- delivered -------------------------------------------------------------------------------------------------

def _sum(q: Table, names: tuple[str, ...], labels: list[str]) -> float | None:
    row = q.row(*names)
    if row is None:
        return None
    values = [row[q.columns.index(l)] if l in q.columns else None for l in labels]
    return None if not values or None in values else sum(values)


def actual_for(t: GuidanceTarget, quarters: Table) -> Actual:
    """The delivered value over the period's reported quarters. A period still in progress gives the value over the
    quarters so far (the tracking value)."""
    labels = resolve_period(t.period)
    names = {"revenue_growth_yoy": REVENUE, "revenue": REVENUE, "ebitda_margin": REVENUE, "pat_growth_yoy": PAT,
             "pat": PAT}.get(t.metric)
    needs = [names, OP_PROFIT] if t.metric == "ebitda_margin" else [names]
    if (labels is None or names is None or UNIT_FOR[t.metric] != t.unit
            or any(quarters.row(*n) is None for n in needs)):
        return Actual(value=None, quarters_in=0, quarters_needed=0)
    reported = [l for l in labels if l in quarters.columns
                and all(quarters.row(*n)[quarters.columns.index(l)] is not None for n in needs)]
    value = None
    if reported:
        current = _sum(quarters, names, reported)
        if t.metric in ("revenue", "pat"):
            value = current
        elif t.metric == "ebitda_margin":
            op = _sum(quarters, OP_PROFIT, reported)
            value = op / current * 100 if current else None
        else:
            prior = _sum(quarters, names, [_year_earlier(l) for l in reported])
            value = (current / prior - 1) * 100 if prior and prior > 0 else None
    return Actual(value=None if value is None else round(value, 1), quarters_in=len(reported),
                  quarters_needed=len(labels))


# ---- verdict ---------------------------------------------------------------------------------------------------

def judge(t: GuidanceTarget, a: Actual) -> Verdict:
    if t.metric == "other" or resolve_period(t.period) is None or a.quarters_needed == 0:
        return "not_checkable"
    if a.quarters_in < a.quarters_needed:
        return "pending"
    if a.value is None:
        return "not_checkable"
    v, x = t.value, a.value
    tol = max(1.0, 0.1 * abs(v)) if t.unit == "pct" else 0.05 * abs(v)
    if t.comparison == "between" and t.value_high is not None:
        # Every checkable metric is higher-is-better, so beating the top of a range is met, not a miss.
        lo = min(v, t.value_high)
        return "met" if x >= lo else "partly" if x >= lo - tol else "missed"
    if t.comparison == "gte":
        return "met" if x >= v else "partly" if x >= v - tol else "missed"
    if t.comparison == "lte":
        return "met" if x <= v else "partly" if x <= v + tol else "missed"
    gap = abs(x - v)  # approx, or a "between" with no upper bound
    return "met" if gap <= tol else "partly" if gap <= 2 * tol else "missed"


# ---- extraction ------------------------------------------------------------------------------------------------

class _Target(BaseModel):
    """Lenient on purpose: one malformed item is dropped on its own instead of failing the whole reply."""
    metric: str = "other"
    raw_metric: str = ""
    comparison: str = ""
    value: float | None = None
    value_high: float | None = None
    unit: str = ""
    period: str = ""
    quote: str = ""
    source_id: str = ""
    forward_looking: bool = False

    def normalised(self, said_on: date) -> GuidanceTarget | None:
        if not self.forward_looking or self.value is None or (self.value == 0 and not self.value_high):
            return None
        if self.comparison not in SYMBOL or self.unit not in ("pct", "cr") or not self.quote:
            return None
        metric = self.metric if self.metric in UNIT_FOR else "other"
        return GuidanceTarget(metric=metric, raw_metric=self.raw_metric or self.metric.replace("_", " "),
                              comparison=self.comparison, value=self.value, value_high=self.value_high,
                              unit=self.unit, period=self.period, quote=self.quote, source_id=self.source_id,
                              said_on=said_on)


class _Targets(BaseModel):
    targets: list[_Target]


_EXTRACT_SYSTEM = ("You extract explicit numeric guidance from an Indian listed company's earnings call transcript. "
                   "Use only the numbered pages provided. Return JSON only.")
_EXTRACT_PROMPT = """The call took place in {month}. Indian fiscal years run April to March: FY27 is April 2026 to \
March 2027, Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar, H1 = Q1+Q2, H2 = Q3+Q4.

List every forward-looking target management states with an explicit number. Skip vague statements ("healthy \
growth", "double digit" without a number is vague), past results, and analysts' questions.
For each target give:
- metric: revenue_growth_yoy | revenue | ebitda_margin | pat_growth_yoy | pat | other (volume growth, capex, \
segment numbers and anything else are "other")
- raw_metric: management's own words for the metric, short
- comparison: gte (at least / more than), lte (at most / below), between (a range), approx (around / about)
- value, and value_high for a range; unit: pct or cr (amounts in Rs crore; convert lakh crore or billion to crore)
- period: FY27, Q3FY27 or H2FY27 style, resolved from the call date ("this year" in {month} is {fy})
- quote: the exact sentence, copied verbatim from the page
- source_id: the id of the page the quote is on, exactly as given
- forward_looking: true only if the quote states what management expects for a future period; false for \
results already reported, for analysts' numbers and for numbers management declines to commit to
Every target needs its own quote; never reuse one target for several quotes.
Return {{"targets": [...]}}, or {{"targets": []}} if there are none.

{pages}"""

_CHUNK_CHARS = 16000
# The bulk model labelled past results and volume growth as revenue targets on the Pidilite Aug 2026 call; the
# reasoning model returned only the real one (the 20-24% margin band). Accuracy matters more than speed here.
EXTRACT_TIER = "reason"


def _fiscal_year(d: date) -> str:
    return f"FY{(d.year + (1 if d.month >= 4 else 0)) % 100:02d}"


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _quote_on_page(quote: str, page: str) -> bool:
    """The quote must really be on the cited page: at least 80% of its words appear there."""
    words, on_page = _words(quote), set(_words(page))
    return bool(words) and sum(w in on_page for w in words) >= 0.8 * len(words)


def extract_targets(doc: DocText, said_on: date, llm: LLM) -> list[GuidanceTarget]:
    """Explicit numeric targets from one transcript (bulk tier). A target whose page id wasn't provided, or whose
    quote isn't on that page, is dropped."""
    pages = {f"T:{said_on.isoformat()}:p{n}": text for n, text in enumerate(doc.pages, start=1) if text.strip()}
    chunks, current = [], ""
    for sid, text in pages.items():
        block = f"[{sid}]\n{text.strip()}\n\n"
        if current and len(current) + len(block) > _CHUNK_CHARS:
            chunks.append(current)
            current = ""
        current += block
    if current:
        chunks.append(current)

    def ask(chunk: str) -> _Targets:
        prompt = _EXTRACT_PROMPT.format(month=said_on.strftime("%B %Y"), fy=_fiscal_year(said_on), pages=chunk)
        return llm.complete_json(EXTRACT_TIER, _EXTRACT_SYSTEM, prompt, _Targets, max_tokens=16384,  # thinking shares it
                                 pool="extract")

    with ThreadPoolExecutor(max_workers=8) as workers:  # the model pool decides how many actually run
        replies = list(workers.map(ask, chunks))
    out = []
    for reply in replies:
        for raw in reply.targets:
            raw.source_id = raw.source_id.strip(" []")
            t = raw.normalised(said_on)
            if t is None or t.source_id not in pages or not _quote_on_page(t.quote, pages[t.source_id]):
                log.info("dropped target %s %s", raw.raw_metric, raw.source_id)
                continue
            out.append(t)
    return out


# ---- assessment ------------------------------------------------------------------------------------------------

class _Line(BaseModel):
    i: int
    text: str


class _Lines(BaseModel):
    lines: list[_Line]


_EXPLAIN_SYSTEM = ("You write one plain-English line per row explaining a guidance verdict that has already been "
                   "decided. Never change or question the verdict. Return JSON only.")
_EXPLAIN_PROMPT = """For each row write one line of at most 120 characters, for an investor, that explains the given \
verdict using only the target and the delivered number. Don't start with the verdict word. Example: "Revenue \
grew 13.1% over the full year, just short of the 15% guided." 
Return {{"lines": [{{"i": 0, "text": "..."}}, ...]}}.

{rows}"""


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    text = f"{value:,.1f}".removesuffix(".0")
    return f"{text}%" if unit == "pct" else f"₹{text} Cr"


def _target_text(t: GuidanceTarget) -> str:
    if t.comparison == "between" and t.value_high is not None:
        return f"{_fmt(t.value, t.unit)}–{_fmt(t.value_high, t.unit)}"
    return f"{SYMBOL[t.comparison]} {_fmt(t.value, t.unit)}"


def _template(r: DeliveryRow) -> str:
    t, a = r.target, r.actual
    delivered = _fmt(a.value, t.unit)
    if r.verdict == "pending" and a.quarters_needed:
        delivered += f" so far ({a.quarters_in} of {a.quarters_needed} quarters)"
    guided = f"Guided {t.raw_metric} {_target_text(t)} for {t.period}"
    if r.verdict == "not_checkable":
        return f"{guided}; not checkable from reported financials."
    return f"{guided}; delivered {delivered}."


_VERDICT_WORDS = {"met": r"\bmet\b|\bachieved\b|\bbeat\b", "missed": r"\bmiss(ed)?\b|\bfell short\b",
                  "pending": r"\bpending\b", "partly": r"\bpartly\b|\bpartially\b"}


def _contradicts(text: str, verdict: Verdict) -> bool:
    """True if the line names a different verdict than the one code decided."""
    lowered = text.lower()
    return any(re.search(pattern, lowered) for v, pattern in _VERDICT_WORDS.items() if v != verdict
               and not (verdict == "partly" and v == "met"))


def explain(rows: list[DeliveryRow], llm: LLM) -> list[str]:
    """One bulk call for all rows; the verdict is given as fixed. Falls back to a template on any failure or on a
    line that contradicts the verdict."""
    fallback = [_template(r) for r in rows]
    todo = [i for i, r in enumerate(rows) if r.verdict != "not_checkable"]
    if not todo:
        return fallback
    listing = "\n".join(
        f"{i}. target: {r.target.raw_metric} {_target_text(r.target)} for {r.target.period} | delivered: "
        f"{_fmt(r.actual.value, r.target.unit)} ({r.actual.quarters_in} of {r.actual.quarters_needed} quarters "
        f"reported) | verdict: {r.verdict}" for i, r in ((i, rows[i]) for i in todo))
    try:
        reply = llm.complete_json("bulk", _EXPLAIN_SYSTEM, _EXPLAIN_PROMPT.format(rows=listing), _Lines,
                                  max_tokens=1500)
    except BudgetExceeded:
        return fallback
    except LLMError as e:
        log.warning("explain failed: %s", e)
        return fallback
    by_index = {line.i: line.text.strip() for line in reply.lines}
    out = []
    for i, r in enumerate(rows):
        text = by_index.get(i, "") if i in todo else ""
        out.append(text if text and len(text) <= 160 and not _contradicts(text, r.verdict) else fallback[i])
    return out


def assess_delivery(targets: list[GuidanceTarget], quarters: Table, llm: LLM) -> list[DeliveryRow]:
    """One row per (metric, period), keeping the most recent statement of each target."""
    latest: dict[tuple, GuidanceTarget] = {}
    for t in sorted(targets, key=lambda t: t.said_on):
        key = (t.metric, t.raw_metric.lower() if t.metric == "other" else "", t.period.upper().replace(" ", ""))
        latest[key] = t
    rows = []
    for t in latest.values():
        a = actual_for(t, quarters)
        rows.append(DeliveryRow(target=t, actual=a, verdict=judge(t, a), explanation=""))
    order = {"missed": 0, "partly": 1, "met": 2, "pending": 3, "not_checkable": 4}
    rows.sort(key=lambda r: (order[r.verdict], -r.target.said_on.toordinal()))
    for r, text in zip(rows, explain(rows, llm)):
        r.explanation = text
    return rows
