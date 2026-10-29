"""Retrieval over FINN's research reports (the Chat tab). Reports only: each dossier becomes small passages that
name their company and carry the citation of the report source they came from, so an answer built on them can
cite pages exactly like the report does."""
import re

from pydantic import BaseModel

from finn.pull.sections import VERDICT_WORDS


class Passage(BaseModel):
    id: str  # "{SYMBOL}#{n}"
    symbol: str
    company: str
    source_id: str  # the dossier's source id: "SCR", "T:2026-08-01:p12", "AR:2026:p73"
    text: str
    url: str | None
    page: int | None


def short_name(name: str) -> str:
    return re.sub(r"\s+(Limited|Ltd\.?)$", "", name.strip(), flags=re.I)


def _num(v: float | None, unit: str = "") -> str | None:
    if v is None:
        return None
    if unit == "x":  # ratios are small: 0.03 must not read as 0
        return f"{v:.2f}".rstrip("0").rstrip(".") + "×"
    text = f"{v:,.1f}".removesuffix(".0")
    return {"%": f"{text}%", "cr": f"₹{text} Cr"}.get(unit, text)


def _sentence(company: str, parts: list[str | None]) -> str | None:
    kept = [p for p in parts if p]
    return f"{company}: {'; '.join(kept)}." if kept else None


def _snapshot_texts(company: str, s: dict) -> list[str]:
    def clause(label: str, value: str | None, extra: str | None = None) -> str | None:
        return None if value is None else f"{label} {value}" + (f" ({extra})" if extra else "")

    growth = lambda v: None if v is None else f"{_num(v, '%')} a year over 3 years"  # noqa: E731
    texts = [
        _sentence(company, [clause("revenue over the last 4 quarters", _num(s.get("revenue_ttm"), "cr"),
                                   growth(s.get("revenue_cagr_3y"))),
                            clause("profit over the last 4 quarters", _num(s.get("pat_ttm"), "cr"),
                                   growth(s.get("pat_cagr_3y")))]),
        _sentence(company, [clause("operating margin", _num(s.get("opm_latest"), "%"),
                                   None if s.get("opm_3y_ago") is None else f"{_num(s['opm_3y_ago'], '%')} three years ago"),
                            clause("return on equity" if s.get("lender") else "return on capital employed",
                                   _num(s.get("roe_latest") if s.get("lender") else s.get("roce_latest"), "%"))]),
        _sentence(company, [clause("debt to equity", _num(s.get("debt_to_equity"), "x")),
                            clause("cash from operations to profit over 3 years", _num(s.get("cfo_to_pat_3y"), "x"))]),
        f"{company} red flags: {'; '.join(s['flags'])}." if s.get("flags") else None,
    ]
    return [t for t in texts if t]


def _target_text(t: dict) -> str:
    unit = "%" if t["unit"] == "pct" else "cr"
    if t["comparison"] == "between" and t.get("value_high") is not None:
        return f"{_num(t['value'], unit)} to {_num(t['value_high'], unit)}"
    word = {"gte": "at least", "lte": "at most", "approx": "about"}.get(t["comparison"], "")
    return f"{word} {_num(t['value'], unit)}".strip()


def chunk_dossier(dossier: dict) -> list[Passage]:
    """Cited passages from one dossier, each naming the company. Unavailable sections and missing values produce
    nothing (never a 0)."""
    symbol = dossier["symbol"]
    company = short_name(dossier.get("name") or symbol)
    cites = {c["source_id"]: c for s in dossier["sections"] for c in s.get("citations", [])}
    pieces: list[tuple[str, str]] = []  # (source_id, text)
    for sec in dossier["sections"]:
        data = sec.get("data")
        if sec.get("status") != "ready" or not data:
            continue
        if sec["section"] == "snapshot":
            pieces += [("SCR", t) for t in _snapshot_texts(company, data)]
        elif sec["section"] == "delivery":
            for r in data.get("rows", []):
                t, a = r["target"], r["actual"]
                unit = "%" if t["unit"] == "pct" else "cr"
                delivered = "" if a.get("value") is None else (
                    f" Delivered {_num(a['value'], unit)} ({a['quarters_in']} of {a['quarters_needed']} quarters).")
                pieces.append((t["source_id"],
                               f"{company} guided {t['raw_metric']} {_target_text(t)} for {t['period']}: "
                               f"\"{t['quote']}\".{delivered} Verdict: {VERDICT_WORDS[r['verdict']]}."))
        elif sec["section"] == "business":
            first = (data.get("source_ids") or ["SCR"])[0]
            if data.get("what_it_does"):
                pieces.append((first, f"{company} business: {data['what_it_does']}"))
            for seg in data.get("segments", []):
                share = "" if seg.get("share_pct") is None else f": {_num(seg['share_pct'], '%')} of revenue"
                pieces.append(((seg.get("source_ids") or [first])[0], f"{company} segment {seg['name']}{share}."))
        elif sec["section"] == "bull_bear":
            for side in ("bull", "bear"):
                for p in data.get(side, []):
                    if p.get("source_ids"):
                        pieces.append((p["source_ids"][0], f"{company} {side} case: {p['text']}"))
    return [Passage(id=f"{symbol}#{n}", symbol=symbol, company=company, source_id=sid, text=text,
                    url=cites.get(sid, {}).get("url"), page=cites.get(sid, {}).get("page"))
            for n, (sid, text) in enumerate(pieces)]
