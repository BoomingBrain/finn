from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel

from finn.llm import LLM, BudgetExceeded, RequestBudget
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
