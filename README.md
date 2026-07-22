# MLMariss YouTube analytics

Unattended collector plus a read-only dashboard.

A GitHub Actions job runs daily, pulls every available YouTube Reporting API
report, and archives each day permanently as a JSON shard. The dashboard reads
those committed files. **There is no login, no API key entry and no OAuth in the
browser** — the page is static and just reads JSON.

## Why this exists

Thumbnail **impressions** and **CTR** do not exist in the YouTube Analytics API
at all. They are only available from the Reporting API's `channel_reach_basic_a1`
bulk report. That API is job-based: you schedule a job, YouTube generates a CSV
per day, and reports expire after 60 days (30 for historical backfill).

**Anything not archived before it expires is gone permanently.** That is the
core job of this repo: capture each report exactly once and keep it forever.

## One-time setup

### 1. Google Cloud Console

Project **661959930559** (or whichever holds your OAuth client).

- **APIs & Services → Library**: enable **YouTube Analytics API** *and*
  **YouTube Reporting API**. Both. The Data API is also needed for video titles.
- **Credentials → Create Credentials → OAuth client ID**:
  - **Desktop app** is easiest — no redirect URI to register.
  - Or reuse the existing **Web application** client, but first add
    `http://localhost:8765/` under *Authorized redirect URIs*. (Plain `http` is
    normally rejected; `localhost` is exempt.) This is a different field from
    *Authorized JavaScript origins*.
- **Google Auth Platform → Audience → Publish app.**

> **Publishing is not optional for unattended use.** While the app is in
> *Testing*, refresh tokens expire after **7 days** and the collector will break
> every week with `invalid_grant`. Publishing an unverified single-user app is
> fine; you self-consent and click past one warning.

### 2. Mint a refresh token

```bash
python scripts/mint_token.py --client-id YOUR_ID --client-secret YOUR_SECRET
```

Standard library only, no `pip install`. A browser opens; consent (click through
the "unverified app" warning); the script prints three values.

### 3. Add repository secrets

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `YT_CLIENT_ID` | from step 2 |
| `YT_CLIENT_SECRET` | from step 2 |
| `YT_REFRESH_TOKEN` | from step 2 |

Never commit these.

### 4. Create the reporting jobs

**Actions → Collect YouTube analytics → Run workflow**, tick **create_jobs**.

This schedules a job per report type. YouTube then:
- backfills roughly the **previous 30 days**, and
- posts a new report daily from now on.

First data appears within **48 hours**. Nothing to do meanwhile.

### 5. Enable Pages

**Settings → Pages → Deploy from branch → `main` / root.**

Private repos need a paid plan for Pages. On the free tier the repo must stay
public — which is fine, since no secrets live in it.

## Daily operation

Runs at **02:00 UTC = 05:00 Riga** (summer). GitHub cron is UTC and ignores DST,
so in winter it lands at 04:00 local; change the cron to `0 3 * * *` if that
matters.

Each run: refresh jobs → list reports → skip anything already archived →
download the rest → write shards → rebuild summaries → commit.

Runs are **idempotent**. Re-running downloads nothing new. Backfill corrections
replace exactly one day's shard, and a failed download is *not* marked archived,
so the next run retries it.

## Layout

```
data/
  reports/<report_type>/<YYYY-MM-DD>.json   permanent archive, one file per day
  summary.json    per-video totals across 7d/28d/90d/365d/all
  daily.json      channel-level daily series
  traffic.json    traffic source breakdown
  videos.json     titles and thumbnails (refreshed, not accumulated)
  state.json      which reports have been archived
scripts/
  auth.py          refresh-token OAuth
  mint_token.py    one-time token minting
  report_types.py  registry of all report types
  collect.py       the collector
  summarize.py     builds dashboard JSON from shards
index.html         read-only dashboard
```

## Manual use

```bash
export YT_CLIENT_ID=... YT_CLIENT_SECRET=... YT_REFRESH_TOKEN=...

python scripts/collect.py --dry-run          # show what would happen
python scripts/collect.py --create-jobs      # create missing jobs
python scripts/collect.py                    # normal run
python scripts/collect.py --only channel_reach_basic_a1
python scripts/summarize.py
```

## A note on averaging

CTR and retention are **recomputed from totals**, never averaged across days or
videos. Averaging percentages weights a 100-impression day the same as a
100,000-impression one.

With real-shaped test data the difference was **7.31% weighted vs 4.97% naive** —
a 2.3-point error. Both `summarize.py` and the dashboard sum impressions and
clicks separately, then divide. Retention is weighted by views the same way.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `invalid_grant` | App still in Testing (7-day token expiry) → publish it, re-mint |
| `has not been used in project` 403 | Reporting API not enabled in Library |
| Dashboard says "no data yet" | Jobs not created, or <48h since creation |
| A report type is skipped | Not available for this channel; harmless |
| `redirect_uri_mismatch` | Web client without `http://localhost:8765/` registered |

## Data retention

The YouTube API Services Developer Policies require stored resource metadata
(titles, thumbnails) to be refreshed or deleted after 30 days, so `videos.json`
is **rewritten** each run rather than accumulated. The aggregate metrics in
`data/reports/` are not resource metadata and are kept indefinitely — that is
the entire point.
