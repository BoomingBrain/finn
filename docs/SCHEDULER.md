# Scheduling

All jobs run on GitHub Actions. GitHub delays or drops `schedule:` runs when it is busy (several were skipped on
28–29 Oct, leaving the Brief 13 hours old), so the schedule is made self-healing rather than trusted:

| Workflow | Schedule (IST) | Job |
|---|---|---|
| `ingest.yml` | Mon–Fri 09:47, 11:47, 13:47, 15:47, 17:47; daily 19:11 | Filings, prices, signals |
| `dossiers.yml` | Daily 20:17 | Refresh the holdings' research when new results, calls or annual reports appear |
| `watchdog.yml` | Every hour at :23 and :53 | Start any job above that is overdue |

- **Off the hour:** every schedule avoids minute 0, where GitHub's load, and so its delays, peak.
- **The watchdog** ([backend/finn/watchdog.py](../backend/finn/watchdog.py), with tests) asks GitHub when each job last started and starts it if overdue:
  - ingest more than 2.5 h old during market hours (Mon–Fri 09:00–18:30) or 14 h otherwise
  - the daily jobs more than 26 h old

  A missed run is caught within about 30 minutes. The watchdog uses the workflow's built-in token, so there is nothing to configure.
- **Extra runs are harmless:** every job is incremental and queues behind its own concurrency group.
- **Failures:** a job that ran and failed is not restarted every half hour. GitHub reports the failure instead.
