"""Exports this project's Claude Code sessions into FINN_BUILD_HISTORY_EXPORT/source_sessions/ for the submission's "AI build history".

For each session: a redacted copy of the raw .jsonl, and a readable Markdown transcript (prompts, replies, and one
line per tool call). Redacts anything key-shaped, every value in .env and the author's email, and refuses to finish if
one survives. Only the sessions listed in BUILD_SESSIONS are exported; other work in this folder isn't part of the
build. Run: python3 scripts/export_history.py"""
import json
import re
import sys
from pathlib import Path

SESSIONS = Path.home() / ".claude/projects/-Users-ayushrai-Downloads-Enam-holdings"
OUT = Path(__file__).resolve().parents[1] / "FINN_BUILD_HISTORY_EXPORT" / "source_sessions"  # update SOURCE_ARCHIVE.md after a re-export
ROOT = Path(__file__).resolve().parents[1]
BUILD_SESSIONS = ["5cc6a662-768e-4653-b659-84ab7b01e825", "df29b36f-b1bf-4d4e-862b-29df1f45cd68"]
SECRET = re.compile(r"(nvapi-|hf_|gh[pousr]_|github_pat_|rnd_|sk-)[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}"
                    r"|[\w.+-]+@gmail\.com|raiayush1306")


def env_values() -> list[str]:
    env = ROOT / ".env"
    pairs = (line.partition("=")[2].strip().strip("\"'") for line in env.read_text().splitlines()) if env.exists() else []
    return [v for v in pairs if len(v) >= 12 and not v.startswith("http")]


def redact(text: str) -> str:
    for value in env_values():
        text = text.replace(value, "<redacted>")
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
    for session in BUILD_SESSIONS:
        path = SESSIONS / f"{session}.jsonl"
        raw, readable = redact(path.read_text()), markdown(path)
        if SECRET.search(raw + readable) or any(v in raw + readable for v in env_values()):
            sys.exit(f"secret survived redaction in {session}: nothing written")
        (OUT / path.name).write_text(raw)
        (OUT / f"{path.stem}.md").write_text(readable)
        print(f"exported {path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
