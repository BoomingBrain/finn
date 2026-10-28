"""Exports this project's Claude Code sessions into docs/build-history/ for the submission's "AI build history".

For each session: a redacted copy of the raw .jsonl, and a readable Markdown transcript (prompts, replies, and one
line per tool call). Redacts anything key-shaped and the author's email. Run: python3 scripts/export_history.py"""
import json
import re
import sys
from pathlib import Path

SESSIONS = Path.home() / ".claude/projects/-Users-ayushrai-Downloads-Enam-holdings"
OUT = Path(__file__).resolve().parents[1] / "docs" / "build-history"
SECRET = re.compile(r"(nvapi-|hf_|gh[pousr]_|sk-)[A-Za-z0-9_-]{16,}|[\w.+-]+@gmail\.com")


def redact(text: str) -> str:
    return SECRET.sub("<redacted>", text)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for p in content or []:
        if p.get("type") == "text":
            parts.append(p["text"])
        elif p.get("type") == "tool_use":
            args = p.get("input", {})
            label = args.get("description") or args.get("file_path") or args.get("skill") or args.get("action") or ""
            parts.append(f"> **{p['name']}** {label}".rstrip())
    return "\n\n".join(parts)


def markdown(path: Path) -> str:
    lines = [f"# Session {path.stem}\n"]
    for raw in path.read_text().splitlines():
        try:
            o = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg = o.get("message") or {}
        if o.get("type") == "user" and not o.get("isMeta"):
            content = msg.get("content")
            if isinstance(content, list) and all(p.get("type") == "tool_result" for p in content):
                continue  # tool output: summarised by the call line above it
            text = _text(content).strip()
            if text and not text.startswith("<system-reminder>"):
                lines.append(f"\n## User — {o.get('timestamp', '')[:16].replace('T', ' ')}\n\n{text}\n")
        elif o.get("type") == "assistant":
            text = _text(msg.get("content")).strip()
            if text:
                lines.append(f"\n{text}\n")
    return redact("\n".join(lines))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted(SESSIONS.glob("*.jsonl")):
        (OUT / path.name).write_text(redact(path.read_text()))
        (OUT / f"{path.stem}.md").write_text(markdown(path))
        print(f"exported {path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
