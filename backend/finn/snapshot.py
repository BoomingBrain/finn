"""Reads and writes the committed JSON snapshots that the deployed app serves."""
import json
import os
import tempfile
from pathlib import Path

from pydantic import TypeAdapter

from finn.models import Bar, EventsFile, PushSnapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "data" / "snapshot"

_Prices = TypeAdapter(dict[str, list[Bar]])


class SnapshotStore:
    def __init__(self, root: Path = DEFAULT_ROOT):
        self.root = Path(root)

    # push.json
    def load_push(self) -> PushSnapshot | None:
        text = self._read("push.json")
        return PushSnapshot.model_validate_json(text) if text else None

    def save_push(self, snapshot: PushSnapshot) -> None:
        self._write("push.json", snapshot.model_dump_json(indent=1))

    # events.json
    def load_events(self) -> EventsFile | None:
        text = self._read("events.json")
        return EventsFile.model_validate_json(text) if text else None

    def save_events(self, feed: EventsFile) -> None:
        self._write("events.json", feed.model_dump_json(indent=1))

    # prices.json
    def load_prices(self) -> dict[str, list[Bar]]:
        text = self._read("prices.json")
        return _Prices.validate_json(text) if text else {}

    def save_prices(self, prices: dict[str, list[Bar]]) -> None:
        self._write("prices.json", _Prices.dump_json(prices, indent=1).decode())

    # screener/{SYM}.json
    def load_company(self, symbol: str) -> dict | None:
        text = self._read(f"screener/{symbol}.json")
        return json.loads(text) if text else None

    def save_company(self, symbol: str, data: dict) -> None:
        self._write(f"screener/{symbol}.json", json.dumps(data, indent=1, ensure_ascii=False))

    # dossiers/{SYM}.json
    def load_dossier(self, symbol: str) -> dict | None:
        text = self._read(f"dossiers/{symbol}.json")
        return json.loads(text) if text else None

    def save_dossier(self, symbol: str, data: dict) -> None:
        self._write(f"dossiers/{symbol}.json", json.dumps(data, indent=1, ensure_ascii=False, default=str))

    def list_dossiers(self) -> list[str]:
        folder = self.root / "dossiers"
        return sorted(p.stem for p in folder.glob("*.json")) if folder.exists() else []

    def _read(self, rel: str) -> str | None:
        path = self.root / rel
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(tmp, 0o644)  # mkstemp creates 0600; snapshots are plain readable data
            os.replace(tmp, path)  # atomic on the same filesystem
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
