import asyncio

from finn.pull.dossier import SectionEvent
from finn.research_hub import ResearchHub, keep_awake


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


def test_keep_awake_pings_only_while_a_build_runs():
    """Render's free tier stops a server after 15 minutes without incoming requests, which killed builds whose
    viewer had left the screen. While a build runs, the server pings its own public URL."""
    async def scenario():
        gates, pings = {}, []
        hub = ResearchHub(slow_build(gates, []), concurrency=1)
        async def ping():
            pings.append(hub.busy)
        awake = asyncio.create_task(keep_awake(hub, ping, interval=0.01))
        await asyncio.sleep(0.03)
        assert pings == []  # idle: let the server sleep
        hub.start("KOTAKBANK")
        await asyncio.sleep(0.05)
        assert pings and all(pings)
        gates["KOTAKBANK"].set()
        await asyncio.sleep(0.05)
        assert not hub.busy
        count = len(pings)
        await asyncio.sleep(0.03)
        assert len(pings) == count
        awake.cancel()
    run(scenario())


def test_a_ping_failure_does_not_stop_keep_awake():
    async def scenario():
        gates, calls = {}, []
        hub = ResearchHub(slow_build(gates, []), concurrency=1)
        async def ping():
            calls.append(1)
            raise OSError("network")
        awake = asyncio.create_task(keep_awake(hub, ping, interval=0.01))
        hub.start("KOTAKBANK")
        await asyncio.sleep(0.05)
        assert len(calls) > 1 and not awake.done()
        awake.cancel()
        gates["KOTAKBANK"].set()
    run(scenario())
