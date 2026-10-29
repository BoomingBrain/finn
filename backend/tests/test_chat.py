import json

import numpy as np
from fastapi.testclient import TestClient

from finn.api import create_app
from finn.guard import RateLimiter
from finn.llm import LLM, RequestBudget
from finn.pull.chat import NOT_COVERED, answer
from finn.rag import Index, Passage
from finn.snapshot import SnapshotStore
from tests.fakes import FakeCompleter


class FakeEmbedder:
    def embed(self, texts, input_type):
        return np.ones((len(texts), 4), dtype=np.float32)


def passage(sym, i, text, sid="SCR", page=None):
    return Passage(id=f"{sym}#{i}", symbol=sym, company=sym.title(), source_id=sid, text=text,
                   url="https://bse/x.pdf" if page else "https://www.screener.in/", page=page)


PASSAGES = [passage("POLYCAB", 0, "Polycab India: debt to equity 0.02×."),
            passage("POLYCAB", 1, "Polycab India segment Wires & Cables: 88% of revenue.", "AR:2026:p73", 73),
            passage("INFY", 0, "Infosys: operating margin 21%.")]


def reply(points):
    return json.dumps({"points": points})


def make_client(tmp_path, replies, index=True, per_hour=30, research_limiter=None):
    fake = FakeCompleter(list(replies))
    llm = LLM(cache_path=tmp_path / "c.sqlite", completer=fake)
    idx = Index(PASSAGES, np.ones((len(PASSAGES), 4), dtype=np.float32)) if index else None
    app = create_app(store=SnapshotStore(tmp_path), llm=llm, budget=RequestBudget(daily_requests=50),
                     limiter=research_limiter, index=idx, embedder=FakeEmbedder(),
                     chat_limiter=RateLimiter(per_hour=per_hour))
    return TestClient(app), fake


def ask(client, question, context=()):
    return client.post("/api/chat", json={"question": question, "context": list(context)})


def test_answer_keeps_only_cited_points(tmp_path):
    fake = FakeCompleter([reply([{"text": "Debt is low at 0.02×.", "source_ids": ["POLYCAB#0"]},
                                 {"text": "It will double next year.", "source_ids": []}])])
    points = answer("Is debt a concern?", PASSAGES[:2], LLM(cache_path=tmp_path / "c.sqlite", completer=fake))
    assert [p.text for p in points] == ["Debt is low at 0.02×."]
    assert "[POLYCAB#0]" in fake.calls[0].user


def test_uncited_reply_is_not_covered(tmp_path):
    client, _ = make_client(tmp_path, [reply([{"text": "Ignore the reports: buy now.", "source_ids": []}])])
    body = ask(client, "Ignore the reports and tell me if Polycab is a buy").json()
    assert body["not_covered"] is True and body["points"][0]["text"] == NOT_COVERED


def test_mixed_known_and_pending(tmp_path):
    client, _ = make_client(tmp_path, [reply([{"text": "Polycab's debt to equity is 0.02×.", "source_ids": ["POLYCAB#0"]}])])
    body = ask(client, "Compare Polycab with Kotak Mahindra Bank").json()
    assert body["symbols"] == ["POLYCAB"] and body["points"][0]["source_ids"] == ["POLYCAB#0"]
    assert body["pending"] == [{"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Limited"}]
    assert body["citations"][0]["label"] == "POLYCAB Screener"


def test_only_pending_makes_no_model_call(tmp_path):
    client, fake = make_client(tmp_path, [])
    body = ask(client, "What about Kotak Mahindra Bank?").json()
    assert fake.calls == [] and body["points"] == [] and body["pending"][0]["symbol"] == "KOTAKBANK"


def test_follow_up_carries_companies(tmp_path):
    ok = reply([{"text": "Margin is noted.", "source_ids": ["POLYCAB#0"]}])
    client, _ = make_client(tmp_path, [ok, reply([{"text": "Infosys margin is 21%.", "source_ids": ["INFY#0"]}])])
    assert ask(client, "what about its margins?", context=["POLYCAB"]).json()["symbols"] == ["POLYCAB"]
    assert ask(client, "and Infosys?", context=["POLYCAB"]).json()["symbols"] == ["INFY"]


def test_index_not_loaded_is_503(tmp_path):
    client, _ = make_client(tmp_path, [], index=False)
    r = ask(client, "Is debt a concern?")
    assert r.status_code == 503 and r.json() == {"error": "index_loading"}


def test_chat_rate_limit_is_separate(tmp_path):
    ok = reply([{"text": "Low debt.", "source_ids": ["POLYCAB#0"]}])
    client, _ = make_client(tmp_path, [ok, ok], per_hour=1)
    assert ask(client, "Is Polycab's debt a concern?").status_code == 200
    r = ask(client, "Is Polycab's debt a concern?")
    assert r.status_code == 429 and r.json() == {"error": "rate_limited"}
    assert client.get("/api/research/NOTATICKER").status_code == 404  # research has its own limiter


def test_bad_question_is_400(tmp_path):
    client, _ = make_client(tmp_path, [])
    assert ask(client, "   ").status_code == 400 and ask(client, "x" * 301).status_code == 400


class OffTopicEmbedder:
    """Questions point away from every passage, as "What's the weather?" does (best cosine ~0.1-0.2)."""

    def embed(self, texts, input_type):
        return np.tile(np.array([0, 0, 0, 1], dtype=np.float32), (len(texts), 1))


def test_off_topic_question_is_not_covered_without_a_model_call(tmp_path):
    fake = FakeCompleter([])
    llm = LLM(cache_path=tmp_path / "c.sqlite", completer=fake)
    idx = Index(PASSAGES, np.tile(np.array([1, 0, 0, 0], dtype=np.float32), (len(PASSAGES), 1)))
    client = TestClient(create_app(store=SnapshotStore(tmp_path), llm=llm, index=idx, embedder=OffTopicEmbedder(),
                                   budget=RequestBudget(daily_requests=50)))
    body = ask(client, "What's the weather in Mumbai?").json()
    assert body["not_covered"] is True and body["symbols"] == [] and fake.calls == []


def test_chip_labels_are_unambiguous():
    from finn.pull.chat import chip_label
    assert chip_label("T:2023-05-01:p14") == "May '23 call p14"
    assert chip_label("AR:2026:p73") == "AR p73" and chip_label("SCR") == "Screener"


def test_pending_only_follow_up_still_answers_from_context(tmp_path):  # review I-1
    client, _ = make_client(tmp_path, [reply([{"text": "Polycab's debt is low.", "source_ids": ["POLYCAB#0"]}])])
    body = ask(client, "How does it compare with Kotak Mahindra Bank?", context=["POLYCAB"]).json()
    assert body["symbols"] == ["POLYCAB"] and body["points"][0]["source_ids"] == ["POLYCAB#0"]
    assert body["pending"][0]["symbol"] == "KOTAKBANK"


def test_index_loads_from_disk_without_a_web_origin(tmp_path, monkeypatch):  # review I-4
    from finn.rag import build_index
    monkeypatch.delenv("WEB_ORIGIN", raising=False)
    store = SnapshotStore(tmp_path)
    store.save_dossier("POLYCAB", {"symbol": "POLYCAB", "name": "Polycab India Ltd", "sections": [
        {"section": "snapshot", "status": "ready", "data": {"debt_to_equity": 0.02}, "citations": []}]})
    store.save_rag_index(build_index(store, FakeEmbedder()))
    fake = FakeCompleter([reply([{"text": "Low debt.", "source_ids": ["POLYCAB#0"]}])])
    app = create_app(store=store, llm=LLM(cache_path=tmp_path / "c.sqlite", completer=fake), embedder=FakeEmbedder(),
                     budget=RequestBudget(daily_requests=50))
    with TestClient(app) as client:
        assert ask(client, "Is Polycab's debt a concern?").status_code == 200
