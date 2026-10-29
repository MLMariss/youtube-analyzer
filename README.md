# MLMariss YouTube analytics

Unattended collector plus a read-only dashboard.

A GitHub Actions job runs daily, pulls every available YouTube Reporting API
report, and archives each day permanently as a JSON shard. The dashboard reads
those committed files. **There is no login, no API key entry and no OAuth in the
browser** — the page is static and just reads JSON.

Every run also flags the videos that need attention — above all the older ones,
which YouTube Studio does not watch — at the top of the dashboard.

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
python mint_token.py --client-id YOUR_ID --client-secret YOUR_SECRET
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

Only `index.html` and the summary files in `data/*.json` are published:
`_config.yml` excludes the raw archive in `data/reports/`, which would
otherwise push the site past GitHub Pages' 1 GB limit.

## Daily operation

Runs at **02:23 UTC** — 05:23 Riga in summer, 04:23 in winter, since GitHub cron
is UTC and ignores DST. The odd minute is deliberate: schedules on the hour
queue behind everyone else's, and at `0 2 * * *` runs started five to seven
hours late.

Each run: refresh jobs → list reports → skip anything already archived →
download the rest → write shards → snapshot public view counts → rebuild
summaries → flag videos that need attention → commit.

Runs are **idempotent**. Re-running downloads nothing new. Backfill corrections
replace exactly one day's shard, and a failed download is *not* marked archived,
so the next run retries it.

## Layout

```
collect.py         the collector
summarize.py       builds dashboard JSON from shards
monitor.py         flags videos that need attention
auth.py            refresh-token OAuth
mint_token.py      one-time token minting
report_types.py    registry of all report types
index.html         read-only dashboard
_config.yml        keeps data/reports/ off the published Pages site
.github/workflows/collect.yml
data/
  reports/<report_type>/<YYYY-MM-DD>.json   permanent archive, one file per day
  summary.json    per-video totals across 7d/28d/90d/365d/all
  daily.json      channel-level daily series
  traffic.json    traffic source breakdown
  videos.json     titles and thumbnails (refreshed, not accumulated)
  snapshots.json  public view/like/comment counts, last 30 days only
  attention.json  what the "Needs attention" panel shows
  state.json      which reports have been archived
```

## Dashboard

`index.html` is a static, read-only page that reads the JSON in `data/`. No
build step, no login — open it (or serve the folder) and it renders.

### Needs attention

The panel at the top watches the whole library, not just new uploads.
`monitor.py` compares each video's last seven complete days with the 28 days
before them and lists what changed enough to act on:

| Group | Flags | Worth doing |
|---|---|---|
| Moving today | public view counter up since the previous run, at least 3× the video's usual daily views | the earliest warning; the analytics follow 2–3 days later |
| Rising · back catalogue | older than 30 days; views (≥25 a week) or impressions (≥300 a week) at least doubled | pinned comment, description refresh, cards or end screens to newer videos, a follow-up |
| Falling | videos past their launch month whose views halved, from at least 8 a day | see which source dropped; lost search is often a title or description fix |
| CTR drop | videos past their launch month, CTR down 25%+ while impressions held steady | thumbnail or title test |
| New uploads | first 28 days, ranked against your other uploads at the same age | — |
| Audience reaction | dislike, comment or unsubscribe spikes | read the comments |
| Rising topics | searches, outside sites and other channels' videos sending at least 3× their usual views | the topic is heating up: cover it again, or update the video it lands on |

Each rising or falling video shows what drove the change: the traffic source
and its top search terms, suggesting videos or referring sites. **New** marks
anything first flagged in this update; *Show in table* opens the video's full
breakdown below. The thresholds sit at the top of `monitor.py`. They were
calibrated on this channel's archive to flag a handful of videos on an
ordinary day and a few dozen on a busy one.

### Table and filters

- **Time window** (`7 days … All time`) sets the period the metrics are
  *measured* over. Every window ends on the newest day with complete data
  (shown as *data through* in the header), not on today: YouTube publishes
  each day two to three days late, so `7 days` is always seven full days, and
  the chart plots exactly the days the totals add up. Windows longer than the
  collected history read the same totals, so with only a couple of months of
  data `90 days`, `365 days` and `All time` will match until more history
  accumulates.
- **Published filter** narrows *which videos* are listed by upload date. Quick
  presets (`Any / 7d / 28d / 90d / 1y`) fill the range; the two date pickers set
  an exact span. Editing a date by hand clears the active preset.
- Other filters: title search, format (Shorts / long-form), traffic source, and
  minimum views. **Reset** clears them all.
- The table opens sorted by **newest upload first**; every column header is
  sortable.
- Clicking a row expands a per-video drilldown: traffic sources, search terms &
  referrers (own-channel referrers show the video title), device & OS and age &
  gender (both ordered so the breakdown reads top-down and youngest-to-oldest).

## Manual use

```bash
export YT_CLIENT_ID=... YT_CLIENT_SECRET=... YT_REFRESH_TOKEN=...

python collect.py --dry-run          # show what would happen
python collect.py --create-jobs      # create missing jobs
python collect.py                    # normal run
python collect.py --only channel_reach_basic_a1
python summarize.py
python monitor.py
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
| Log says *Not offered by YouTube* | Deprecated report, or a wrong id in `report_types.py`; a following *missing from report_types.py* line names the id YouTube does offer |
| `redirect_uri_mismatch` | Web client without `http://localhost:8765/` registered |

## Data retention

The YouTube API Services Developer Policies require stored resource metadata
(titles, thumbnails) to be refreshed or deleted after 30 days, so `videos.json`
is **rewritten** each run rather than accumulated. For the same reason
`snapshots.json` keeps each video's public view, like and comment counts for
the last 30 days only, which is all the same-day signal needs. The aggregate metrics in
`data/reports/` are not resource metadata and are kept indefinitely — that is
the entire point.
