"""Live research builds, shared and queued.

- At most `concurrency` builds run at once (the free NVIDIA tier handles ~2 reasoning-heavy builds); the rest wait
  in line and are told their position whenever it changes.
- One build per symbol: a second request for a symbol already building joins it and replays what is done so far.
- A build runs as its own task, so a viewer leaving doesn't stop it; it finishes and is handed to `on_complete`.

Every listener receives (kind, payload) tuples: ("queued", {"ahead": n}), ("progress", {...}),
("section", SectionEvent), ("end", None) or ("error", Exception)."""
import asyncio
import logging
from typing import AsyncIterator, Awaitable, Callable

from finn.pull.dossier import SectionEvent

log = logging.getLogger(__name__)

RunBuild = Callable[[str, Callable[[dict], None]], AsyncIterator[SectionEvent]]


class Build:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.history: list[tuple[str, object]] = []
        self.listeners: list[asyncio.Queue] = []
        self.finished = False

    def publish(self, kind: str, payload: object) -> None:
        if kind == "queued" and self.history and self.history[-1][0] == "queued":
            self.history[-1] = (kind, payload)  # a late joiner only needs the current position
        else:
            self.history.append((kind, payload))
        for q in self.listeners:
            q.put_nowait((kind, payload))

    def listen(self) -> asyncio.Queue:
        """A queue that starts with everything published so far, then receives what comes next."""
        q: asyncio.Queue = asyncio.Queue()
        for item in self.history:
            q.put_nowait(item)
        self.listeners.append(q)
        return q

    def leave(self, q: asyncio.Queue) -> None:
        if q in self.listeners:
            self.listeners.remove(q)


class ResearchHub:
    def __init__(self, run_build: RunBuild, concurrency: int = 2,
                 on_complete: Callable[[str, list[SectionEvent]], Awaitable[None]] | None = None):
        self.run_build = run_build
        self.concurrency = concurrency
        self.on_complete = on_complete
        self.builds: dict[str, Build] = {}
        self.waiting: list[Build] = []
        self.running = 0
        self._slots: asyncio.Semaphore | None = None  # created on the running loop

    def get(self, symbol: str) -> Build | None:
        return self.builds.get(symbol)

    def start(self, symbol: str) -> Build:
        """The running build for `symbol`, or a new one queued behind the current ones."""
        if symbol in self.builds:
            return self.builds[symbol]
        if self._slots is None:
            self._slots = asyncio.Semaphore(self.concurrency)
        build = self.builds[symbol] = Build(symbol)
        self.waiting.append(build)
        self._announce_queue()
        asyncio.get_running_loop().create_task(self._run(build))
        return build

    def _announce_queue(self) -> None:
        """Each waiting build learns how many builds must finish before it starts (0 = starting now)."""
        for i, b in enumerate(self.waiting):
            b.publish("queued", {"ahead": max(0, self.running + i - self.concurrency + 1)})

    async def _run(self, build: Build) -> None:
        loop = asyncio.get_running_loop()

        def report(step: dict) -> None:  # called from the loop or from worker threads
            try:
                on_loop = asyncio.get_running_loop() is loop
            except RuntimeError:
                on_loop = False
            if on_loop:
                build.publish("progress", step)
            else:
                loop.call_soon_threadsafe(build.publish, "progress", step)

        sections: list[SectionEvent] = []
        try:
            async with self._slots:
                self.waiting.remove(build)
                self.running += 1
                self._announce_queue()
                try:
                    async for event in self.run_build(build.symbol, report):
                        sections.append(event)
                        build.publish("section", event)
                finally:
                    self.running -= 1
            if self.on_complete:  # before "end", so a viewer told "done" can rely on it being saved
                await self.on_complete(build.symbol, sections)
            build.publish("end", None)
        except Exception as e:
            log.warning("live research for %s failed: %r", build.symbol, e)
            build.publish("error", e)
        finally:
            if build in self.waiting:
                self.waiting.remove(build)
                self._announce_queue()
            build.finished = True
            self.builds.pop(build.symbol, None)
