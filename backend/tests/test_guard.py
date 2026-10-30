import json

from fastapi.testclient import TestClient

from finn.api import create_app
from finn.guard import RateLimiter, write_symbols
from finn.llm import RequestBudget
from finn.pull.dossier import SectionEvent
from finn.snapshot import SnapshotStore
from finn.sources.screener import SourceUnreachable


def test_limiter_denies_fourth_in_hour():
    limiter = RateLimiter(per_hour=3)
    assert [limiter.allow("1.2.3.4", now=t) for t in (0, 10, 20, 30)] == [True, True, True, False]


def test_limiter_allows_after_window():
    limiter = RateLimiter(per_hour=3)
    for t in (0, 10, 20):
        limiter.allow("1.2.3.4", now=t)
    assert limiter.allow("1.2.3.4", now=3599) is False
    assert limiter.allow("1.2.3.4", now=3601) is True  # the call at t=0 has left the window


def test_limiter_keys_independent():
    limiter = RateLimiter(per_hour=1)
    assert limiter.allow("a", now=0) and limiter.allow("b", now=0)
    assert not limiter.allow("a", now=1)


def section(name: str) -> SectionEvent:
    return SectionEvent(section=name, status="ready", data={"name": name})


async def fake_build(symbol, llm, progress=None, **kwargs):
    for i, name in enumerate(("snapshot", "delivery", "business", "bull_bear")):
        if progress:
            progress({"done": i, "total": 4, "label": f"Working on {name}"})
        yield section(name)


async def unreachable_build(symbol, llm, progress=None, **kwargs):
    raise SourceUnreachable("screener.in: ConnectTimeout")
    yield  # an async generator, like build_dossier


class FakeSaved:
    def __init__(self, files=None):
        self.files = dict(files or {})

    def load(self, symbol):
        return self.files.get(symbol)

    def save(self, symbol, dossier):
        self.files[symbol] = dossier
        return True


def client(tmp_path, build=fake_build, per_hour=3, budget=10, saved=None) -> TestClient:
    store = SnapshotStore(tmp_path)
    store.save_dossier("PIDILITIND", {"symbol": "PIDILITIND", "sections": [section("snapshot").model_dump()]})
    app = create_app(store=store, build=build, limiter=RateLimiter(per_hour=per_hour),
                     budget=RequestBudget(daily_requests=budget), llm=object(), saved=saved or FakeSaved())
    return TestClient(app)


def events(response, keep_queued: bool = False) -> list[tuple[str, str]]:
    """(event name, data) pairs from an SSE body; keep-alive comments (and queue positions) are skipped."""
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = [l for l in block.splitlines() if not l.startswith(":")]
        if lines:
            name = next((l[7:] for l in lines if l.startswith("event: ")), "message")
            data = next((l[6:] for l in lines if l.startswith("data: ")), "")
            if name != "queued" or keep_queued:
                out.append((name, data))
    return out


def test_precomputed_replays_without_limits(tmp_path):
    c = client(tmp_path, per_hour=0, budget=0)
    r = c.get("/api/research/pidilitind")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert [n for n, _ in events(r)] == ["message", "done"]


def test_unknown_symbol_404(tmp_path):
    r = client(tmp_path).get("/api/research/NOTATICKER")
    assert r.status_code == 404 and r.json() == {"error": "unknown_symbol"}


def test_live_build_streams_sections_in_order(tmp_path):
    r = client(tmp_path).get("/api/research/KOTAKBANK")
    sent = events(r)
    progress = [json.loads(d) for n, d in sent if n == "progress"]
    assert [p["done"] for p in progress] == [0, 1, 2, 3] and progress[0]["label"] == "Working on snapshot"
    sent = [e for e in sent if e[0] != "progress"]
    assert [json.loads(d)["section"] for n, d in sent if n == "message"] == ["snapshot", "delivery", "business",
                                                                            "bull_bear"]
    assert sent[-1][0] == "done"


def test_fourth_live_ticker_is_rate_limited(tmp_path):
    c = client(tmp_path)
    for s in ("KOTAKBANK", "ITC", "TCS"):
        assert c.get(f"/api/research/{s}", headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"}).status_code == 200
    r = c.get("/api/research/WIPRO", headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 429 and r.json() == {"error": "rate_limited"}
    assert c.get("/api/research/KOTAKBANK", headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200  # cached
    assert c.get("/api/research/WIPRO", headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 200


def test_budget_exhausted(tmp_path):
    r = client(tmp_path, budget=0).get("/api/research/KOTAKBANK")
    assert r.status_code == 429 and r.json() == {"error": "budget_exhausted"}


def test_sources_unreachable_sends_error_event(tmp_path):
    sent = events(client(tmp_path, build=unreachable_build).get("/api/research/KOTAKBANK"))
    assert sent == [("error", json.dumps({"code": "sources_unreachable",
                                          "message": "Couldn't fetch sources for KOTAKBANK from the server."}))]


def test_symbols_json_marks_precomputed(tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_dossier("PIDILITIND", {"symbol": "PIDILITIND", "sections": []})
    assert write_symbols(store) > 2000
    rows = {r["symbol"]: r for r in json.loads((tmp_path / "symbols.json").read_text())}
    assert rows["PIDILITIND"]["precomputed"] is True and rows["KOTAKBANK"]["precomputed"] is False
    assert rows["KOTAKBANK"]["name"] == "Kotak Mahindra Bank Limited"


def test_live_build_is_saved_and_replayed_after_restart(tmp_path):
    saved = FakeSaved()
    client(tmp_path, saved=saved).get("/api/research/KOTAKBANK")
    assert [sec["section"] for sec in saved.files["KOTAKBANK"]["sections"]] == ["snapshot", "delivery", "business",
                                                                                "bull_bear"]
    restarted = client(tmp_path, build=unreachable_build, per_hour=0, budget=0, saved=saved)  # fresh process
    sent = events(restarted.get("/api/research/KOTAKBANK"))
    assert [n for n, _ in sent] == ["message"] * 4 + ["done"]


async def failing_section_build(symbol, llm, progress=None, **kwargs):
    yield section("snapshot")
    yield SectionEvent(section="delivery", status="unavailable", reason="Analysis failed")


def test_dossier_with_failed_section_is_not_saved(tmp_path):
    saved = FakeSaved()
    client(tmp_path, build=failing_section_build, saved=saved).get("/api/research/KOTAKBANK")
    assert saved.files == {}


async def crashing_build(symbol, llm, progress=None, **kwargs):
    yield section("snapshot")
    raise RuntimeError("worker died")


def test_unexpected_failure_ends_with_an_error_event(tmp_path):
    sent = events(client(tmp_path, build=crashing_build).get("/api/research/KOTAKBANK"))
    assert sent[0][0] == "message" and sent[-1][0] == "error"
    assert json.loads(sent[-1][1])["code"] == "failed"


def test_live_stream_starts_with_queue_position(tmp_path):
    sent = events(client(tmp_path).get("/api/research/KOTAKBANK"), keep_queued=True)
    assert sent[0] == ("queued", json.dumps({"ahead": 0}))


def test_keep_awake_starts_only_on_render(tmp_path, monkeypatch):
    from finn import api
    started = []

    async def fake_keep_awake(hub, ping, interval=240):
        started.append(ping.args)

    monkeypatch.setattr(api, "keep_awake", fake_keep_awake)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    with TestClient(create_app(store=SnapshotStore(tmp_path))):
        pass
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://finn.onrender.com")
    with TestClient(create_app(store=SnapshotStore(tmp_path))):
        pass
    assert started == [("https://finn.onrender.com",)]
