import asyncio

from finn.pull.dossier import SectionEvent
from finn.research_hub import ResearchHub


def run(coro):
    return asyncio.run(coro)


def slow_build(gates: dict, calls: list):
    async def build(symbol, report):
        calls.append(symbol)
        report({"done": 1, "total": 2, "label": "Reading"})
        yield SectionEvent(section="snapshot", status="ready", data={"name": symbol})
        await gates.setdefault(symbol, asyncio.Event()).wait()
        yield SectionEvent(section="bull_bear", status="ready", data={})
    return build


async def drain(q) -> list:
    out = []
    while True:
        kind, payload = await asyncio.wait_for(q.get(), 2)
        out.append((kind, payload))
        if kind in ("end", "error"):
            return out


def test_second_request_for_same_symbol_joins_the_build():
    async def scenario():
        gates, calls, done = {}, [], []
        async def complete(symbol, sections):
            done.append((symbol, len(sections)))
        hub = ResearchHub(slow_build(gates, calls), concurrency=2, on_complete=complete)
        first = hub.start("KOTAKBANK").listen()
        await asyncio.sleep(0.01)
        late = hub.start("KOTAKBANK").listen()  # replays what already happened
        gates.setdefault("KOTAKBANK", asyncio.Event()).set()
        a, b = await drain(first), await drain(late)
        assert calls == ["KOTAKBANK"] and done == [("KOTAKBANK", 2)]
        assert [k for k, _ in a if k != "queued"] == [k for k, _ in b if k != "queued"] == \
            ["progress", "section", "section", "end"]
        assert hub.get("KOTAKBANK") is None  # finished builds leave the hub
    run(scenario())


def test_builds_beyond_the_limit_wait_in_line():
    async def scenario():
        gates, calls = {}, []
        hub = ResearchHub(slow_build(gates, calls), concurrency=1)
        a = hub.start("A").listen()
        await asyncio.sleep(0.01)
        b = hub.start("B").listen()
        c = hub.start("C").listen()
        await asyncio.sleep(0.01)
        assert calls == ["A"]
        assert (await b.get()) == ("queued", {"ahead": 1}) and (await c.get()) == ("queued", {"ahead": 2})
        gates.setdefault("A", asyncio.Event()).set()
        await drain(a)
        events_b = []
        while True:  # B starts; C moves up to "1 ahead"
            kind, payload = await asyncio.wait_for(b.get(), 2)
            events_b.append((kind, payload))
            if kind == "section":
                break
        assert [k for k, _ in events_b] == ["queued", "progress", "section"] and calls == ["A", "B"]  # started
        assert ("queued", {"ahead": 1}) in [await c.get() for _ in range(c.qsize())]
        gates.setdefault("B", asyncio.Event()).set()
        gates.setdefault("C", asyncio.Event()).set()
        await drain(c)
    run(scenario())


def test_a_viewer_leaving_does_not_stop_the_build():
    async def scenario():
        gates, calls, done = {}, [], []
        async def complete(symbol, sections):
            done.append(symbol)
        hub = ResearchHub(slow_build(gates, calls), on_complete=complete)
        build = hub.start("X")
        q = build.listen()
        build.leave(q)
        gates.setdefault("X", asyncio.Event()).set()
        for _ in range(50):
            if done:
                break
            await asyncio.sleep(0.01)
        assert done == ["X"]
    run(scenario())


def test_failure_reaches_every_listener():
    async def scenario():
        async def broken(symbol, report):
            raise ConnectionError("screener down")
            yield
        hub = ResearchHub(broken)
        events = await drain(hub.start("X").listen())
        assert events[-1][0] == "error" and isinstance(events[-1][1], ConnectionError)
    run(scenario())
