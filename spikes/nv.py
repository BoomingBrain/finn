"""Tiny NVIDIA API helper shared by spikes. Reads NVIDIA_API_KEY from ../.env (tolerates spaces)."""
from pathlib import Path

import httpx

BASE = "https://integrate.api.nvidia.com/v1"


def api_key() -> str:
    for line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
        if "=" in line and line.split("=", 1)[0].strip() == "NVIDIA_API_KEY":
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("NVIDIA_API_KEY missing from .env")


def chat(model: str, messages: list, timeout: float = 180, **extra) -> dict:
    r = httpx.post(f"{BASE}/chat/completions", timeout=timeout,
                   headers={"Authorization": f"Bearer {api_key()}", "Accept": "application/json"},
                   json={"model": model, "messages": messages, **extra})
    if r.status_code != 200:
        raise RuntimeError(f"{model}: HTTP {r.status_code} {r.text[:300]}")
    return r.json()
