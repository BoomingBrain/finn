"""Retrieval over FINN's research reports (the Chat tab). Reports only: each dossier becomes small passages that
name their company and carry the citation of the report source they came from, so an answer built on them can
cite pages exactly like the report does."""
import argparse
import base64
import hashlib
import logging
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
import numpy as np
from pydantic import BaseModel

from finn.llm import load_api_key
from finn.pull.sections import VERDICT_WORDS
from finn.snapshot import REPO_ROOT, SnapshotStore

log = logging.getLogger(__name__)

EMBED_MODEL = "nvidia/nemotron-3.5-embed-1b"  # 1.4 s a call; the 8B model took 14 s (29 Oct)
EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
EMBED_CACHE = REPO_ROOT / "backend" / ".cache" / "embeddings.sqlite"
BATCH = 64


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


# ---- retrieval -------------------------------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9]+")


def bm25(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Okapi BM25 of `query` against each doc, lowercase word tokens."""
    q = set(_WORD.findall(query.lower()))
    toks = [_WORD.findall(d.lower()) for d in docs]
    if not q or not toks:
        return [0.0] * len(docs)
    n, avg = len(toks), (sum(map(len, toks)) / len(toks)) or 1.0
    df = {t: sum(1 for d in toks if t in d) for t in q}
    scores = []
    for d in toks:
        s = 0.0
        for t in q:
            f = d.count(t)
            if f:
                idf = np.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / avg))
        scores.append(float(s))
    return scores


class Index:
    """Passages plus L2-normalised vectors; hybrid search = 0.6 cosine + 0.4 BM25 (scaled to its maximum)."""

    def __init__(self, passages: list[Passage], vectors: np.ndarray):
        self.passages = list(passages)
        self.vectors = self._normalise(np.asarray(vectors, dtype=np.float32).reshape(len(passages), -1))

    @staticmethod
    def _normalise(m: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(m, axis=1, keepdims=True) if m.size else m
        return m / np.where(norms == 0, 1, norms) if m.size else m

    @classmethod
    def from_dict(cls, d: dict) -> "Index":
        passages = [Passage(**p) for p in d["passages"]]
        raw = np.frombuffer(base64.b64decode(d["vectors"]), dtype=np.float16).astype(np.float32)
        return cls(passages, raw.reshape(len(passages), -1) if passages else np.zeros((0, 0)))

    def add(self, passages: list[Passage], vectors: np.ndarray) -> None:
        """Adds or replaces a company's passages (a dossier saved by live research)."""
        symbols = {p.symbol for p in passages}
        keep = [i for i, p in enumerate(self.passages) if p.symbol not in symbols]
        new = self._normalise(np.asarray(vectors, dtype=np.float32).reshape(len(passages), -1))
        old = self.vectors[keep] if keep else np.zeros((0, new.shape[1]), dtype=np.float32)
        self.passages = [self.passages[i] for i in keep] + list(passages)
        self.vectors = np.vstack([old, new]) if len(old) else new

    def best_cosine(self, query_vec: np.ndarray) -> float:
        """How close the question comes to anything researched; off-topic questions score far lower."""
        if not self.passages:
            return 0.0
        q = np.asarray(query_vec, dtype=np.float32)
        return float((self.vectors @ (q / (np.linalg.norm(q) or 1))).max())

    @property
    def symbols(self) -> set[str]:
        return {p.symbol for p in self.passages}

    def search(self, query_vec: np.ndarray, query_text: str, symbols: set[str] | None = None, k: int = 12,
               per_company: int = 4) -> list[Passage]:
        idx = [i for i, p in enumerate(self.passages) if symbols is None or p.symbol in symbols]
        if not idx:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1)
        cosine = self.vectors[idx] @ q
        lexical = np.array(bm25(query_text, [self.passages[i].text for i in idx]))
        lexical = lexical / lexical.max() if lexical.max() > 0 else lexical
        order = np.argsort(-(0.6 * cosine + 0.4 * lexical), kind="stable")
        # No company named: at most `per_company` each. Several named: they share the k slots, so a comparison
        # sees every company instead of the strongest one crowding the rest out.
        cap = per_company if symbols is None else max(1, k // len(symbols))
        out, per = [], {}
        for j in order:
            p = self.passages[idx[j]]
            if per.get(p.symbol, 0) >= cap:
                continue
            per[p.symbol] = per.get(p.symbol, 0) + 1
            out.append(p)
            if len(out) == k:
                break
        return out


def _name_keys(name: str) -> str:
    return re.sub(r"\s*\(india\)\s*$", "", short_name(name), flags=re.I).lower()


def find_companies(question: str, researched: dict[str, str], nse: dict[str, str]) -> tuple[list[str], list[tuple[str, str]]]:
    """(researched symbols named, unresearched (symbol, name) named). Symbols match as whole upper-case words; names
    match whole-phrase without "Limited/Ltd" and "(India)", or by a distinctive first word (one NSE company only)."""
    text = question.lower()
    firsts: dict[str, list[str]] = {}
    for sym, name in nse.items():
        firsts.setdefault(_name_keys(name).split(" ")[0], []).append(sym)

    def named(sym: str, name: str, short_symbols_ok: bool) -> bool:
        if (len(sym) >= 4 or short_symbols_ok) and re.search(rf"(?<![A-Za-z0-9]){re.escape(sym)}(?![A-Za-z0-9])", question):
            return True
        key = _name_keys(name)
        if key and re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", text):
            return True
        first = key.split(" ")[0]
        return (len(first) >= 5 and firsts.get(first) == [sym]
                and re.search(rf"(?<![a-z0-9]){re.escape(first)}(?![a-z0-9])", text) is not None)

    found = [s for s, n in researched.items() if named(s, n, short_symbols_ok=True)]
    pending = [(s, n) for s, n in nse.items() if s not in researched and named(s, n, short_symbols_ok=False)]
    return found, pending


# ---- embeddings and the index ----------------------------------------------------------------------------------

class Embedder:
    """NVIDIA embeddings, batched and cached by exact text, so a rebuild only pays for new passages."""

    def __init__(self, api_key: str | None = None, cache_path: Path = EMBED_CACHE, client: httpx.Client | None = None):
        self.api_key = api_key or load_api_key()
        self.client = client or httpx.Client(timeout=60)
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(cache_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS emb (key TEXT PRIMARY KEY, vec BLOB NOT NULL)")
        self._lock = threading.Lock()

    @staticmethod
    def _key(text: str, input_type: str) -> str:
        return hashlib.sha256(f"{EMBED_MODEL}|{input_type}|{text}".encode()).hexdigest()

    def _request(self, texts: list[str], input_type: str) -> list[list[float]]:
        body = {"model": EMBED_MODEL, "input": texts, "input_type": input_type, "encoding_format": "float"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(2):
            r = self.client.post(EMBED_URL, json=body, headers=headers)
            if (r.status_code == 429 or r.status_code >= 500) and attempt == 0:
                time.sleep(5)
                continue
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]
        raise RuntimeError("unreachable")

    def embed(self, texts: list[str], input_type: Literal["passage", "query"]) -> np.ndarray:
        keys = [self._key(t, input_type) for t in texts]
        with self._lock:
            cached = {k: np.frombuffer(v, dtype=np.float32) for k, v in self._db.execute(
                f"SELECT key, vec FROM emb WHERE key IN ({','.join('?' * len(keys))})", keys)} if keys else {}
        missing = [i for i, k in enumerate(keys) if k not in cached]
        for start in range(0, len(missing), BATCH):
            batch = missing[start:start + BATCH]
            vectors = self._request([texts[i] for i in batch], input_type)
            with self._lock:
                for i, v in zip(batch, vectors):
                    arr = np.asarray(v, dtype=np.float32)
                    cached[keys[i]] = arr
                    self._db.execute("INSERT OR REPLACE INTO emb VALUES (?, ?)", (keys[i], arr.tobytes()))
                self._db.commit()
        return np.stack([cached[k] for k in keys]) if keys else np.zeros((0, 0), dtype=np.float32)


def build_index(store: SnapshotStore, embedder) -> dict:
    """Every researched dossier's passages with their vectors (float16, base64) for the Chat tab."""
    passages = [p for sym in store.list_dossiers() for p in chunk_dossier(store.load_dossier(sym))]
    vectors = embedder.embed([p.text for p in passages], "passage") if passages else np.zeros((0, 0))
    return {"model": EMBED_MODEL, "dim": int(vectors.shape[1]) if passages else 0,
            "built_at": datetime.now(timezone.utc).isoformat(), "passages": [p.model_dump() for p in passages],
            "vectors": base64.b64encode(vectors.astype(np.float16).tobytes()).decode()}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Build the Chat retrieval index from the research dossiers")
    parser.add_argument("--build", action="store_true")
    if not parser.parse_args().build:
        parser.error("pass --build")
    store = SnapshotStore()
    index = build_index(store, Embedder())
    store.save_rag_index(index)
    log.info("indexed %d passages from %d dossiers", len(index["passages"]), len(store.list_dossiers()))


if __name__ == "__main__":
    main()
