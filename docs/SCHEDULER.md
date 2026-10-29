# Reliable scheduling with cron-job.org

GitHub Actions' built-in `schedule:` trigger skipped or delayed several runs on this repository (28–29 Oct), so the
Brief's data went 13 hours without a refresh. An external scheduler starts each workflow on time through GitHub's
API instead. The workflows don't change: each already accepts a manual start (`workflow_dispatch`).

## 1. Create a GitHub token that can only start workflows

GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token:

- **Name:** `finn-scheduler`; **Expiration:** 90 days.
- **Repository access:** Only select repositories → `BoomingBrain/finn`.
- **Permissions → Repository → Actions:** Read and write. Nothing else.

This token can start and read workflow runs and nothing more: it can't read code, push or change secrets.

## 2. Test the token once

```bash
curl -i -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/BoomingBrain/finn/actions/workflows/ingest.yml/dispatches \
  -d '{"ref":"main"}'
```

Expected: `HTTP/2 204`. A new "ingest" run appears under the repository's Actions tab.

## 3. Create the jobs on cron-job.org

Sign up at cron-job.org. In Settings, set the time zone to **Asia/Kolkata**. Create one job per row:

| Job | URL (POST) | Schedule (IST) |
|---|---|---|
| FINN ingest, market hours | `https://api.github.com/repos/BoomingBrain/finn/actions/workflows/ingest.yml/dispatches` | Mon–Fri at 09:30, 11:30, 13:30, 15:30, 17:30 |
| FINN ingest, evening | same URL | Every day at 19:00 |
| FINN holdings refresh | `https://api.github.com/repos/BoomingBrain/finn/actions/workflows/dossiers.yml/dispatches` | Every day at 20:00 |
| FINN prebuild (optional) | `https://api.github.com/repos/BoomingBrain/finn/actions/workflows/prebuild.yml/dispatches` | Every day at 02:30 |

For every job, under **Advanced**:

- **Request method:** POST
- **Headers:**
  - `Authorization: Bearer <TOKEN>`
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2022-11-28`
  - `Content-Type: application/json`
- **Request body:** `{"ref":"main"}`
- **Success:** treat HTTP 204 as success, and turn on failure notifications so an expired token gets noticed.

## 4. After the first scheduled run succeeds

The workflows' own `schedule:` lines are then removed, so runs aren't duplicated. Duplicates would be harmless,
because each workflow queues behind its own concurrency group and ingestion is incremental, but they waste Actions
minutes. Renew the token before it expires (cron-job.org will email on the first failed call).
