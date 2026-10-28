"""One gateway for every LLM call: routes each job to the right free NVIDIA model, throttles to stay
under the free-tier rate limit, caches every response and enforces a daily request budget."""
import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from finn.snapshot import REPO_ROOT

Tier = Literal["vision", "bulk", "reason"]
TIER_MODELS: dict[str, str] = {
    "vision": "nvidia/nemotron-3.5-super-vl-120b-a12b",
    "bulk": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "reason": "nvidia/nemotron-3-ultra-550b-a55b",
}
# Thinking burns ~125 hidden tokens even on trivial replies; only the reason tier keeps it.
THINKING: dict[str, bool] = {"vision": False, "bulk": False, "reason": True}
# Calls in flight per tier. The 550B reasoning model timed out and returned 429s with ~16 parallel calls
# (dossier precompute, 28 Oct); the smaller models handled the same load.
CONCURRENCY: dict[str, int] = {"vision": 4, "bulk": 6, "reason": 2}

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_CACHE = REPO_ROOT / "backend" / ".cache" / "llm.sqlite"

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class BudgetExceeded(Exception):
    pass


def model_for(tier: str) -> str:
    """The model for a tier; `FINN_MODEL_<TIER>` overrides it so a vanished model is a config change."""
    return os.environ.get(f"FINN_MODEL_{tier.upper()}", TIER_MODELS[tier])


class Completer(Protocol):
    def __call__(self, model: str, system: str, user: str, images: list[bytes], max_tokens: int,
                 thinking: bool) -> tuple[str, int, int]:
        """Returns (text, input_tokens, output_tokens)."""


class RequestBudget:
    """Caps model requests per UTC day. The free tier costs nothing; the shared rate limit is what runs out."""

    def __init__(self, daily_requests: int, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.daily_requests = daily_requests
        self.clock = clock
        self._day = None
        self._count = 0
        self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            self._roll()
            if self._count >= self.daily_requests:
                raise BudgetExceeded(f"daily LLM request budget of {self.daily_requests} reached")

    def record(self, model: str, in_tok: int, out_tok: int) -> None:
        with self._lock:
            self._roll()
            self._count += 1

    def _roll(self) -> None:
        today = self.clock().astimezone(timezone.utc).date()
        if today != self._day:
            self._day, self._count = today, 0


class Throttle:
    """Spaces calls evenly so all models together stay under `per_minute`."""

    def __init__(self, per_minute: int = 35, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.interval = 60.0 / per_minute
        self.clock = clock
        self.sleep = sleep
        self._next_at = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self.clock()
            if now < self._next_at:
                self.sleep(self._next_at - now)
            self._next_at = max(now, self._next_at) + self.interval


def load_api_key() -> str:
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    env_file = REPO_ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "NVIDIA_API_KEY":
                key = value.strip().strip("\"'")
    if not key:
        raise LLMError("NVIDIA_API_KEY is not set (environment or .env)")
    return key


class NvidiaCompleter:
    """Calls NVIDIA's OpenAI-compatible chat completions endpoint."""

    def __init__(self, api_key: str | None = None, timeout: float = 120, thinking_timeout: float = 300,
                 retry_waits: tuple[float, ...] = (5, 20, 60)):
        self.api_key = api_key or load_api_key()
        self.timeout = timeout
        self.thinking_timeout = thinking_timeout
        self.retry_waits = retry_waits

    def __call__(self, model, system, user, images, max_tokens, thinking):
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(img).decode()}}
                   for img in images]
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": content + [{"type": "text", "text": user}] if images else user}]
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
        if not thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        waits = list(self.retry_waits)
        while True:
            try:
                r = httpx.post(NVIDIA_URL, json=body, headers=headers,
                               timeout=self.thinking_timeout if thinking else self.timeout)
            except httpx.HTTPError as e:
                if waits:
                    time.sleep(waits.pop(0))
                    continue
                raise LLMError(f"{model}: {type(e).__name__}: {e}") from e
            if (r.status_code == 429 or r.status_code >= 500) and waits:
                time.sleep(waits.pop(0))
                continue
            if r.status_code != 200:
                raise LLMError(f"{model}: HTTP {r.status_code} {r.text[:300]}")
            data = r.json()
            usage = data.get("usage") or {}
            text = data["choices"][0]["message"].get("content") or ""
            return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def close_truncated(text: str) -> str:
    """Closes the brackets a reply left open when it hit its token limit, e.g. '{"targets": [{...}' gains ']}'.
    Only complete items survive validation; a reply cut mid-string is returned unchanged."""
    stack, in_string, escaped = [], False, False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    if in_string:
        return text
    return text.rstrip().rstrip(",") + "".join(reversed(stack))


def _extract_json(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON object in reply")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start:end + 1]


class LLM:
    def __init__(self, cache_path: Path = DEFAULT_CACHE, completer: Completer | None = None,
                 budget: RequestBudget | None = None, throttle: Throttle | None = None):
        self._completer = completer
        self.budget = budget
        self.throttle = throttle or (Throttle() if completer is None else None)
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(cache_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS usage (model TEXT PRIMARY KEY, calls INTEGER, "
                         "input_tokens INTEGER, output_tokens INTEGER)")
        self._db.commit()
        self._lock = threading.Lock()
        self._slots = {tier: threading.BoundedSemaphore(int(os.environ.get(f"FINN_CONCURRENCY_{tier.upper()}", n)))
                       for tier, n in CONCURRENCY.items()}

    @property
    def completer(self) -> Completer:
        if self._completer is None:  # created lazily so a server with only cached data needs no key
            self._completer = NvidiaCompleter()
        return self._completer

    def complete_json(self, tier: Tier, system: str, user: str, schema: type[T], images: list[bytes] = [],
                      max_tokens: int = 2048) -> T:
        model = model_for(tier)
        key = hashlib.sha256("|".join(
            [model, system, user, schema.__name__] + [hashlib.sha256(i).hexdigest() for i in images]).encode()).hexdigest()
        with self._lock:
            row = self._db.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        if row:
            return schema.model_validate_json(row[0])

        prompt, error = user, None
        for _ in range(2):
            with self._slots[tier]:
                text = self._call(model, system, prompt, images, max_tokens, THINKING.get(tier, False))
            try:
                try:
                    result = schema.model_validate_json(_extract_json(text))
                except (ValidationError, ValueError):
                    result = schema.model_validate_json(close_truncated(text[text.find("{"):]))
            except (ValidationError, ValueError) as e:
                error = e
                prompt = (f"{user}\n\nYour previous reply was not valid: {str(e)[:500]}\n"
                          f"Reply with ONLY JSON matching this schema: {json.dumps(schema.model_json_schema())}")
                continue
            with self._lock:
                self._db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (key, result.model_dump_json()))
                self._db.commit()
            return result
        raise LLMError(f"{model} returned invalid JSON twice: {error}")

    def usage(self) -> dict[str, dict[str, int]]:
        with self._lock:
            rows = self._db.execute("SELECT model, calls, input_tokens, output_tokens FROM usage").fetchall()
        return {m: {"calls": c, "input_tokens": i, "output_tokens": o} for m, c, i, o in rows}

    def _call(self, model, system, user, images, max_tokens, thinking) -> str:
        if self.budget:
            self.budget.check()
        if self.throttle:
            self.throttle.wait()
        text, in_tok, out_tok = self.completer(model, system, user, images, max_tokens, thinking)
        if self.budget:
            self.budget.record(model, in_tok, out_tok)
        with self._lock:
            self._db.execute(
                "INSERT INTO usage VALUES (?, 1, ?, ?) ON CONFLICT(model) DO UPDATE SET calls = calls + 1, "
                "input_tokens = input_tokens + excluded.input_tokens, output_tokens = output_tokens + excluded.output_tokens",
                (model, in_tok, out_tok))
            self._db.commit()
        return text
