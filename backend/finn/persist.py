"""Permanent home for dossiers built live on the server: the GitHub repo itself, next to the precomputed ones.

Render's disk is wiped on every restart, so a live dossier is committed to data/snapshot/dossiers/{SYM}.json through
GitHub's contents API. The next scheduled deploy ships it to the static site (instant for everyone); until then the
server finds it here and replays it instead of rebuilding. Without GITHUB_TOKEN this is a no-op."""
import base64
import json
import logging
import os

import httpx

log = logging.getLogger(__name__)
API = "https://api.github.com"


class GitHubStore:
    def __init__(self, token: str | None, repo: str, branch: str = "main", client: httpx.Client | None = None):
        self.token, self.repo, self.branch = token, repo, branch
        self.client = client or httpx.Client(timeout=20)

    @classmethod
    def from_env(cls) -> "GitHubStore":
        return cls(os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPO", "BoomingBrain/finn"),
                   os.environ.get("GITHUB_BRANCH", "main"))

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _url(self, symbol: str) -> str:
        return f"{API}/repos/{self.repo}/contents/data/snapshot/dossiers/{symbol}.json"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}

    def _get(self, symbol: str) -> tuple[dict | None, str | None]:
        r = self.client.get(self._url(symbol), headers=self._headers(), params={"ref": self.branch})
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        body = r.json()
        return json.loads(base64.b64decode(body["content"])), body["sha"]

    def load(self, symbol: str) -> dict | None:
        if not self.enabled:
            return None
        try:
            return self._get(symbol)[0]
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("saved dossier lookup failed for %s: %r", symbol, e)
            return None

    def save(self, symbol: str, dossier: dict) -> bool:
        """Creates or replaces the file in one commit. Returns False (and logs) on any failure."""
        if not self.enabled:
            return False
        try:
            _, sha = self._get(symbol)
            content = json.dumps(dossier, indent=1, ensure_ascii=False, default=str).encode()
            body = {"message": f"chore: save live dossier {symbol}", "branch": self.branch,
                    "content": base64.b64encode(content).decode(),
                    "committer": {"name": "finn-research[bot]", "email": "github-actions[bot]@users.noreply.github.com"}}
            if sha:
                body["sha"] = sha
            self.client.put(self._url(symbol), headers=self._headers(), json=body).raise_for_status()
            return True
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("saving dossier %s failed: %r", symbol, e)
            return False
