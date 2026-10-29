"""Self-healing schedule. GitHub drops or delays `schedule:` runs when busy (it skipped several on 28-29 Oct), so a
watchdog workflow runs twice an hour, asks GitHub when each job last started, and starts any that are overdue.
Every job is incremental, so an extra run costs a few Actions minutes and nothing else.

Run in Actions: `python -m finn.watchdog` with GITHUB_TOKEN (actions: write) and GITHUB_REPOSITORY set."""
import logging
import os
from datetime import datetime, time, timedelta

import httpx

from finn.models import IST

log = logging.getLogger(__name__)

MARKET_OPEN, MARKET_CLOSE = time(9, 0), time(18, 30)
DAILY = timedelta(hours=26)  # a day plus slack for a late run
MAX_AGE = {"dossiers": DAILY}
WORKFLOWS = {"ingest": "ingest.yml", "dossiers": "dossiers.yml"}


def overdue(job: str, last_started: datetime | None, now: datetime) -> bool:
    """True if `job` should have started again by `now`. Ingest runs every 2 h in market hours (Mon-Fri 09:00-18:30
    IST), so 2.5 h without a run is overdue then; outside them the 19:00 run carries the night, so 14 h is."""
    if last_started is None:
        return True
    local = now.astimezone(IST)
    if job == "ingest":
        market = local.weekday() < 5 and MARKET_OPEN <= local.time() <= MARKET_CLOSE
        limit = timedelta(hours=2, minutes=30) if market else timedelta(hours=14)
    else:
        limit = MAX_AGE[job]
    return now - last_started > limit


def _last_started(client: httpx.Client, repo: str, workflow: str) -> datetime | None:
    """Start time of the most recent run, whatever its result: a failed job is reported by GitHub, not retried here
    every half hour."""
    r = client.get(f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs", params={"per_page": 1})
    r.raise_for_status()
    runs = r.json()["workflow_runs"]
    return datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00")) if runs else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo = os.environ["GITHUB_REPOSITORY"]
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    now = datetime.now(IST)
    with httpx.Client(headers=headers, timeout=30) as client:
        for job, workflow in WORKFLOWS.items():
            last = _last_started(client, repo, workflow)
            if overdue(job, last, now):
                client.post(f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
                            json={"ref": "main"}).raise_for_status()
                log.info("%s: last started %s, overdue: started it", job, last)
            else:
                log.info("%s: last started %s, on time", job, last)


if __name__ == "__main__":
    main()
