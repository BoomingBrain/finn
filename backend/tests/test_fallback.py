import httpx
import pytest

from finn import llm
from finn.llm import FALLBACK_MODEL, FallbackCompleter, GeminiCompleter, LLMError, NvidiaCompleter, default_completer


class Failing:
    def __call__(self, model, system, user, images, max_tokens, thinking):
        raise LLMError(f"{model}: HTTP 429")


class Recording:
    def __init__(self):
        self.calls = []

    def __call__(self, model, system, user, images, max_tokens, thinking):
        self.calls.append(model)
        return '{"ok": true}', 1, 1


def test_falls_back_to_gemini_when_nvidia_fails():
    gemini = Recording()
    completer = FallbackCompleter(Failing(), gemini)
    assert completer("nvidia/nemotron-3-ultra-550b-a55b", "", "q", [], 100, True)[0] == '{"ok": true}'
    assert gemini.calls == [FALLBACK_MODEL]
    assert completer.fallbacks == 1


def test_nvidia_answer_skips_the_fallback():
    nvidia, gemini = Recording(), Recording()
    FallbackCompleter(nvidia, gemini)("m", "", "q", [], 100, False)
    assert nvidia.calls == ["m"] and gemini.calls == []


def test_fallback_failure_reports_both_errors():
    with pytest.raises(LLMError, match="HTTP 429.*fallback"):
        FallbackCompleter(Failing(), Failing())("m", "", "q", [], 100, False)


def test_no_gemini_key_means_no_fallback(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "n")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr(llm, "read_env_file", lambda name: "")
    assert isinstance(default_completer(), NvidiaCompleter)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert isinstance(default_completer(), FallbackCompleter)


def test_gemini_request_shape(monkeypatch):
    sent = {}

    def post(url, json, headers, timeout):
        sent.update(url=url, body=json)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 2}})

    monkeypatch.setattr(httpx, "post", post)
    assert GeminiCompleter(api_key="g")(FALLBACK_MODEL, "s", "u", [], 100, False) == ("{}", 3, 2)
    assert "generativelanguage.googleapis.com" in sent["url"]
    assert "chat_template_kwargs" not in sent["body"]  # NVIDIA-only field
    assert sent["body"]["reasoning_effort"] == "low"


def test_daily_quota_fails_fast_without_retrying(monkeypatch):
    calls = []

    def post(url, json, headers, timeout):
        calls.append(1)
        return httpx.Response(429, text='{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}')

    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(LLMError, match="429"):
        GeminiCompleter(api_key="g", retry_waits=(0, 0, 0))(FALLBACK_MODEL, "s", "u", [], 100, False)
    assert calls == [1]
