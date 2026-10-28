import base64
import json

import httpx

from finn.persist import GitHubStore


def github(files: dict[str, dict], calls: list):
    """A fake contents API over an in-memory dict."""
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        name = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET":
            if name not in files:
                return httpx.Response(404, json={"message": "Not Found"})
            raw = json.dumps(files[name]["data"]).encode()
            return httpx.Response(200, json={"content": base64.b64encode(raw).decode(), "sha": files[name]["sha"]})
        body = json.loads(request.content)
        if name in files and body.get("sha") != files[name]["sha"]:
            return httpx.Response(409, json={"message": "sha mismatch"})
        files[name] = {"data": json.loads(base64.b64decode(body["content"])), "sha": f"sha{len(calls)}"}
        return httpx.Response(201, json={})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_save_then_load_round_trip():
    files, calls = {}, []
    store = GitHubStore("t", "o/r", client=github(files, calls))
    assert store.save("KOTAKBANK", {"symbol": "KOTAKBANK", "sections": []})
    assert store.load("KOTAKBANK") == {"symbol": "KOTAKBANK", "sections": []}
    assert calls[1].url.path == "/repos/o/r/contents/data/snapshot/dossiers/KOTAKBANK.json"


def test_save_replaces_existing_with_its_sha():
    files, calls = {"X.json": {"data": {"v": 1}, "sha": "abc"}}, []
    store = GitHubStore("t", "o/r", client=github(files, calls))
    assert store.save("X", {"v": 2})
    assert json.loads(calls[-1].content)["sha"] == "abc" and files["X.json"]["data"] == {"v": 2}


def test_without_token_is_a_no_op():
    calls = []
    store = GitHubStore(None, "o/r", client=github({}, calls))
    assert store.load("X") is None and store.save("X", {}) is False and calls == []


def test_github_outage_does_not_raise():
    down = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    store = GitHubStore("t", "o/r", client=down)
    assert store.load("X") is None and store.save("X", {}) is False
