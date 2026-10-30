"""One gateway for every LLM call: routes each job to the right free NVIDIA model, throttles to stay
under the free-tier rate limit, caches every response and enforces a daily request budget."""
import base64
import hashlib
import json
import logging
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
# Model pools: a job sent to a pool runs on whichever member has a free slot, each member capped at
# POOL_CONCURRENCY calls in flight. Capacity is per model on the free tier, so a pool multiplies parallelism.
# Members must pass `make eval` for the job; FINN_POOL_<NAME>="model,model" overrides.
POOLS: dict[str, list[str]] = {"extract": [TIER_MODELS["reason"]]}
POOL_CONCURRENCY = 2


def pool_models(name: str) -> list[str]:
    env = os.environ.get(f"FINN_POOL_{name.upper()}")
    return [m.strip() for m in env.split(",") if m.strip()] if env else POOLS[name]


class ModelPool:
    """Hands out the first member with a free slot, waiting until one frees up."""

    def __init__(self, models: list[str], per_model: int = POOL_CONCURRENCY):
        self.free = {m: per_model for m in models}
        self._cond = threading.Condition()

    def acquire(self) -> str:
        with self._cond:
            while True:
                model = next((m for m, n in self.free.items() if n > 0), None)
                if model:
                    self.free[model] -= 1
                    return model
                self._cond.wait()

    def release(self, model: str) -> None:
        with self._cond:
            self.free[model] += 1
            self._cond.notify()

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Fallback when NVIDIA still fails after its retries, used only if GEMINI_API_KEY is set. Checked 30 Oct on the free
# tier: gemini-3.5-flash answers in ~3 s and reads images; the Pro models have no free quota.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
FALLBACK_MODEL = "gemini-3.5-flash"
DEFAULT_CACHE = REPO_ROOT / "backend" / ".cache" / "llm.sqlite"

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger(__name__)


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


def read_env_file(name: str) -> str:
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip().strip("\"'")
    return ""


def load_api_key(name: str = "NVIDIA_API_KEY", required: bool = True) -> str:
    key = os.environ.get(name, "").strip() or read_env_file(name)
    if not key and required:
        raise LLMError(f"{name} is not set (environment or .env)")
    return key


class NvidiaCompleter:
    """Calls NVIDIA's OpenAI-compatible chat completions endpoint."""
    url = NVIDIA_URL
    key_name = "NVIDIA_API_KEY"

    def __init__(self, api_key: str | None = None, timeout: float = 120, thinking_timeout: float = 300,
                 retry_waits: tuple[float, ...] = (5, 20, 60)):
        self.api_key = api_key or load_api_key(self.key_name)
        self.timeout = timeout
        self.thinking_timeout = thinking_timeout
        self.retry_waits = retry_waits

    def __call__(self, model, system, user, images, max_tokens, thinking):
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(img).decode()}}
                   for img in images]
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": content + [{"type": "text", "text": user}] if images else user}]
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
        self._configure_thinking(body, thinking)
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        waits = list(self.retry_waits)
        while True:
            try:
                r = httpx.post(self.url, json=body, headers=headers,
                               timeout=self.thinking_timeout if thinking else self.timeout)
            except httpx.HTTPError as e:
                if waits:
                    time.sleep(waits.pop(0))
                    continue
                raise LLMError(f"{model}: {type(e).__name__}: {e}") from e
            daily_quota_gone = r.status_code == 429 and "PerDay" in r.text  # resets tomorrow: retrying wastes minutes
            if (r.status_code == 429 or r.status_code >= 500) and waits and not daily_quota_gone:
                time.sleep(waits.pop(0))
                continue
            if r.status_code != 200:
                raise LLMError(f"{model}: HTTP {r.status_code} {r.text[:300]}")
            data = r.json()
            usage = data.get("usage") or {}
            text = data["choices"][0]["message"].get("content") or ""
            return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    def _configure_thinking(self, body: dict, thinking: bool) -> None:
        if not thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}


class GeminiCompleter(NvidiaCompleter):
    """Gemini's OpenAI-compatible endpoint. Its models always think a little; "low" keeps that from eating the
    reply's token budget on the steps that don't need it."""
    url = GEMINI_URL
    key_name = "GEMINI_API_KEY"

    def _configure_thinking(self, body: dict, thinking: bool) -> None:
        if not thinking:
            body["reasoning_effort"] = "low"


class FallbackCompleter:
    """NVIDIA first; if it still fails after its own retries, the same prompt goes to FALLBACK_MODEL. Answers
    pass the same JSON validation and citation guard either way."""

    def __init__(self, primary: Completer, fallback: Completer):
        self.primary, self.fallback = primary, fallback
        self.fallbacks = 0

    def __call__(self, model, system, user, images, max_tokens, thinking):
        try:
            return self.primary(model, system, user, images, max_tokens, thinking)
        except LLMError as e:
            log.warning("%s failed (%s); falling back to %s", model, str(e)[:200], FALLBACK_MODEL)
            self.fallbacks += 1
            try:
                return self.fallback(FALLBACK_MODEL, system, user, images, max_tokens, thinking)
            except LLMError as f:
                raise LLMError(f"{e}; fallback {f}") from f


def default_completer() -> Completer:
    nvidia = NvidiaCompleter()
    gemini_key = load_api_key("GEMINI_API_KEY", required=False)
    return FallbackCompleter(nvidia, GeminiCompleter(api_key=gemini_key)) if gemini_key else nvidia


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
        self._pools: dict[str, ModelPool] = {}

    @property
    def completer(self) -> Completer:
        if self._completer is None:  # created lazily so a server with only cached data needs no key
            self._completer = default_completer()
        return self._completer

    def _key(self, model: str, system: str, user: str, schema: type, images: list[bytes]) -> str:
        return hashlib.sha256("|".join(
            [model, system, user, schema.__name__] + [hashlib.sha256(i).hexdigest() for i in images]).encode()).hexdigest()

    def _pool(self, name: str) -> ModelPool:
        with self._lock:
            if name not in self._pools:
                self._pools[name] = ModelPool(pool_models(name))
            return self._pools[name]

    def complete_json(self, tier: Tier, system: str, user: str, schema: type[T], images: list[bytes] = [],
                      max_tokens: int = 2048, pool: str | None = None) -> T:
        """`pool` runs the job on whichever pool member is free (see POOLS); a cached answer from any member is
        reused, so moving work between members never pays twice."""
        candidates = pool_models(pool) if pool else [model_for(tier)]
        for m in candidates:
            with self._lock:
                row = self._db.execute("SELECT value FROM cache WHERE key = ?",
                                       (self._key(m, system, user, schema, images),)).fetchone()
            if row:
                return schema.model_validate_json(row[0])

        prompt, error, model = user, None, candidates[0]
        for _ in range(2):
            if pool:
                model = self._pool(pool).acquire()
                try:
                    text = self._call(model, system, prompt, images, max_tokens, THINKING.get(tier, False))
                finally:
                    self._pool(pool).release(model)
            else:
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
                self._db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)",
                                 (self._key(model, system, user, schema, images), result.model_dump_json()))
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
