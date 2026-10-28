import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel

from finn.llm import CONCURRENCY, LLM, BudgetExceeded, RequestBudget, close_truncated
from tests.fakes import FakeCompleter


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class Answer(BaseModel):
    ok: bool


def test_budget_blocks_after_cap():
    budget = RequestBudget(daily_requests=2, clock=Clock(datetime(2026, 10, 28, 10, tzinfo=timezone.utc)))
    budget.record("m", 10, 5)
    budget.check()
    budget.record("m", 10, 5)
    with pytest.raises(BudgetExceeded):
        budget.check()


def test_budget_resets_next_day():
    clock = Clock(datetime(2026, 10, 28, 23, 50, tzinfo=timezone.utc))
    budget = RequestBudget(daily_requests=2, clock=clock)
    budget.record("m", 10, 5)
    budget.record("m", 10, 5)
    with pytest.raises(BudgetExceeded):
        budget.check()
    clock.now += timedelta(minutes=15)  # past UTC midnight
    budget.check()


def test_llm_checks_budget_before_calling(tmp_path):
    budget = RequestBudget(daily_requests=1)
    budget.record("m", 10, 5)
    fake = FakeCompleter(responses=['{"ok": true}'])
    llm = LLM(cache_path=tmp_path / "llm.sqlite", completer=fake, budget=budget)
    with pytest.raises(BudgetExceeded):
        llm.complete_json("bulk", "system", "user", Answer)
    assert fake.calls == []


def test_reason_tier_calls_are_capped(tmp_path):
    class Reply(BaseModel):
        ok: bool

    state = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def slow(model, system, user, images, max_tokens, thinking):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return '{"ok": true}', 1, 1

    llm = LLM(cache_path=tmp_path / "llm.sqlite", completer=slow)
    threads = [threading.Thread(target=llm.complete_json, args=("reason", "s", f"u{i}", Reply)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert state["peak"] == CONCURRENCY["reason"]


def test_truncated_json_keeps_complete_items(tmp_path):
    class Items(BaseModel):
        targets: list[dict]

    cut = '{"targets": [{"a": 1, "q": "x}y"},\n {"a": 2}'  # hit the token limit after the second item
    assert close_truncated(cut) == '{"targets": [{"a": 1, "q": "x}y"},\n {"a": 2}]}'
    assert close_truncated('{"targets": [{"q": "cut mid') == '{"targets": [{"q": "cut mid'  # mid-string: unchanged
    assert close_truncated('{"t": [{"q": "say \\"hi\\" [ok"}') == '{"t": [{"q": "say \\"hi\\" [ok"}]}'  # escaped quotes
    llm = LLM(cache_path=tmp_path / "llm.sqlite", completer=FakeCompleter([cut]))
    assert llm.complete_json("bulk", "s", "u", Items).targets == [{"a": 1, "q": "x}y"}, {"a": 2}]
