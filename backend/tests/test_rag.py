from finn.rag import Passage, chunk_dossier


def dossier(**overrides) -> dict:
    snapshot = {"name": "Polycab India Ltd", "lender": False, "revenue_ttm": 31000.0, "pat_ttm": 2900.0,
                "revenue_cagr_3y": 22.4, "pat_cagr_3y": 30.1, "opm_latest": 14.2, "opm_3y_ago": 12.9,
                "roce_latest": 29.0, "roe_latest": 21.0, "debt_to_equity": 0.03, "cfo_to_pat_3y": 0.9,
                "quarterly": [], "flags": []}
    row = {"target": {"metric": "revenue_growth_yoy", "raw_metric": "revenue growth", "comparison": "gte",
                      "value": 20, "value_high": None, "unit": "pct", "period": "FY26",
                      "quote": "We expect 20% growth this year", "source_id": "T:2025-05-01:p4",
                      "said_on": "2025-05-01"},
           "actual": {"value": None, "quarters_in": 0, "quarters_needed": 0}, "verdict": "not_checkable",
           "explanation": ""}
    d = {"symbol": "POLYCAB", "name": "Polycab India Ltd", "sections": [
        {"section": "snapshot", "status": "ready", "reason": None, "data": snapshot,
         "citations": [{"source_id": "SCR", "url": "https://www.screener.in/company/POLYCAB/", "page": None}]},
        {"section": "delivery", "status": "ready", "reason": None, "data": {"transcripts": [], "rows": [row]},
         "citations": [{"source_id": "T:2025-05-01:p4", "url": "https://bse/t.pdf", "page": 4}]},
        {"section": "business", "status": "ready", "reason": None,
         "data": {"what_it_does": "Makes wires and cables.", "source_ids": ["AR:2026:p73"],
                  "segments": [{"name": "Wires & Cables", "share_pct": 88.0, "source_ids": ["AR:2026:p73"]}]},
         "citations": [{"source_id": "AR:2026:p73", "url": "https://bse/ar.pdf", "page": 73}]},
        {"section": "bull_bear", "status": "ready", "reason": None,
         "data": {"bull": [{"text": "Debt-free balance sheet.", "source_ids": ["SCR"]}],
                  "bear": [{"text": "Copper prices squeeze margins.", "source_ids": ["AR:2026:p73"]}]},
         "citations": []},
    ]}
    d.update(overrides)
    return d


def test_every_passage_names_the_company():
    passages = chunk_dossier(dossier())
    assert passages and all(p.text.startswith("Polycab India") for p in passages)
    assert len({p.id for p in passages}) == len(passages) and passages[0].id == "POLYCAB#0"


def test_snapshot_skips_missing_values():
    d = dossier()
    d["sections"][0]["data"]["debt_to_equity"] = None
    d["sections"][0]["data"]["cfo_to_pat_3y"] = None
    text = " ".join(p.text for p in chunk_dossier(d) if p.source_id == "SCR" and " case:" not in p.text)  # snapshot only
    assert "debt" not in text.lower() and " 0 " not in text


def test_delivery_passage_has_quote_and_plain_verdict():
    [p] = [p for p in chunk_dossier(dossier()) if p.source_id == "T:2025-05-01:p4"]
    assert "We expect 20% growth this year" in p.text and "cannot be checked" in p.text
    assert "not_checkable" not in p.text


def test_passages_carry_citation_page():
    ar = [p for p in chunk_dossier(dossier()) if p.source_id == "AR:2026:p73"]
    assert ar and all((p.url, p.page) == ("https://bse/ar.pdf", 73) for p in ar)


def test_unavailable_sections_produce_nothing():
    d = dossier()
    d["sections"][1] = {"section": "delivery", "status": "unavailable", "reason": "No concall transcripts on screener.in",
                        "data": None, "citations": []}
    assert not [p for p in chunk_dossier(d) if p.source_id.startswith("T:")]
    assert isinstance(chunk_dossier(d)[0], Passage)


def test_ratios_keep_two_decimals():
    text = " ".join(p.text for p in chunk_dossier(dossier()))
    assert "debt to equity 0.03×" in text and "0.9×" in text


# ---- Task 2: embedder and index ------------------------------------------------------------------------------

import base64  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402

import httpx  # noqa: E402
import numpy as np  # noqa: E402

from finn.rag import Embedder, build_index  # noqa: E402
from finn.snapshot import SnapshotStore  # noqa: E402


class FakeEmbedder:
    dim = 8

    def embed(self, texts, input_type):
        return np.array([[b / 255 for b in hashlib.sha256(t.encode()).digest()[: self.dim]] for t in texts],
                        dtype=np.float32)


def test_build_index_round_trips_vectors(tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_dossier("POLYCAB", dossier())
    index = build_index(store, FakeEmbedder())
    vectors = np.frombuffer(base64.b64decode(index["vectors"]), dtype=np.float16).reshape(len(index["passages"]), -1)
    expected = FakeEmbedder().embed([p["text"] for p in index["passages"]], "passage")
    assert vectors.shape == (len(index["passages"]), 8) and np.allclose(vectors, expected, atol=1e-3)
    assert index["model"] == "nvidia/nemotron-3.5-embed-1b" and index["dim"] == 8


def _transport(calls):
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]} for _ in body["input"]]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embedder_caches(tmp_path):
    calls = []
    e = Embedder("k", tmp_path / "emb.sqlite", client=_transport(calls))
    e.embed(["a", "b"], "passage")
    out = e.embed(["a", "b"], "passage")
    assert len(calls) == 1 and out.shape == (2, 3)


def test_embedder_batches_by_64(tmp_path):
    calls = []
    Embedder("k", tmp_path / "emb.sqlite", client=_transport(calls)).embed([f"t{i}" for i in range(130)], "passage")
    assert [len(c["input"]) for c in calls] == [64, 64, 2]
    assert calls[0]["input_type"] == "passage" and calls[0]["model"] == "nvidia/nemotron-3.5-embed-1b"


# ---- Task 3: retrieval and company detection -------------------------------------------------------------------

from finn.rag import Index, bm25, find_companies  # noqa: E402


def _p(i, symbol, text):
    return Passage(id=f"{symbol}#{i}", symbol=symbol, company=symbol.title(), source_id="SCR", text=text, url=None,
                   page=None)


def _index(passages, vectors):
    return Index(passages, np.asarray(vectors, dtype=np.float32))


def test_search_restricts_to_named_companies():
    idx = _index([_p(0, "INFY", "Infosys margin 21%"), _p(0, "TCS", "TCS margin 25%")], [[1, 0], [1, 0]])
    hits = idx.search(np.array([1, 0], dtype=np.float32), "margin", symbols={"TCS"})
    assert [h.symbol for h in hits] == ["TCS"]


def test_search_caps_per_company_when_none_named():
    passages = [_p(i, "POLYCAB", f"Polycab debt point {i}") for i in range(10)] + [_p(0, "INFY", "Infosys debt")]
    idx = _index(passages, [[1, 0]] * 11)
    hits = idx.search(np.array([1, 0], dtype=np.float32), "debt", k=12, per_company=4)
    assert sum(h.symbol == "POLYCAB" for h in hits) == 4 and any(h.symbol == "INFY" for h in hits)


def test_bm25_prefers_exact_terms():
    idx = _index([_p(0, "A", "A revenue grew strongly"), _p(1, "A", "A debt to equity is 1.4")], [[1, 0], [1, 0]])
    assert idx.search(np.array([1, 0], dtype=np.float32), "debt to equity")[0].id == "A#1"
    assert bm25("debt", ["no match here", "debt debt"])[1] > 0 and bm25("debt", ["x"]) == [0.0]


NSE = {"POLYCAB": "Polycab India Limited", "INFY": "Infosys Limited", "LT": "Larsen & Toubro Limited",
       "ITC": "ITC Limited", "KOTAKBANK": "Kotak Mahindra Bank Limited"}
RESEARCHED = {"POLYCAB": "Polycab India Limited", "INFY": "Infosys Limited", "LT": "Larsen & Toubro Limited",
              "ITC": "ITC Limited"}


def test_find_companies_by_symbol_and_name():
    assert find_companies("Is Polycab's debt high?", RESEARCHED, NSE)[0] == ["POLYCAB"]
    assert find_companies("INFY margins", RESEARCHED, NSE)[0] == ["INFY"]
    assert find_companies("How is Larsen & Toubro doing?", RESEARCHED, NSE)[0] == ["LT"]


def test_symbol_match_needs_word_boundary():
    assert find_companies("results switch", RESEARCHED, NSE) == ([], [])


def test_unresearched_company_is_pending():
    found, pending = find_companies("What about Kotak Mahindra Bank?", RESEARCHED, NSE)
    assert found == [] and pending == [("KOTAKBANK", "Kotak Mahindra Bank Limited")]


def test_named_companies_share_the_results():
    passages = [_p(i, "PERSISTENT", f"Persistent margin point {i}") for i in range(12)] + \
               [_p(i, "INFY", f"Infosys margin point {i}") for i in range(3)]
    idx = _index(passages, [[1, 0]] * 12 + [[0.9, 0.1]] * 3)
    hits = idx.search(np.array([1, 0], dtype=np.float32), "margin", symbols={"PERSISTENT", "INFY"}, k=12)
    assert sum(h.symbol == "INFY" for h in hits) == 3 and sum(h.symbol == "PERSISTENT" for h in hits) == 6
