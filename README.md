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
| `SERPAPI_KEY` | optional, for *Discover*: the API key from a free [SerpApi](https://serpapi.com) account (*Your Account → API Key*) |

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
download the rest → write shards → snapshot public view counts and each
video's title/description/tag/thumbnail fingerprint → rebuild summaries → flag
videos that need attention → measure logged and detected actions → search
Google Trends for what is not on the dashboard yet → commit.

Runs are **idempotent**. Re-running downloads nothing new. Backfill corrections
replace exactly one day's shard, and a failed download is *not* marked archived,
so the next run retries it.

## Layout

```
collect.py         the collector
summarize.py       builds dashboard JSON from shards
monitor.py         flags videos that need attention, with next steps
signals.py         week-on-week and shift tests (shared)
patches.py         Steam updates behind a change, and patches touching a video
actions.py         the learning loop: logs, measures, remembers
discover.py        what is not on the dashboard yet (Discover); also applies Dismiss and Set forms
trends.py          Google Trends through SerpApi, and the search budget
auth.py            refresh-token OAuth
mint_token.py      one-time token minting
report_types.py    registry of all report types
index.html         read-only dashboard
_config.yml        keeps the raw archives off the published Pages site
docs/search-demand-plan.md   the Discover roadmap, phase by phase
.github/workflows/collect.yml
.github/ISSUE_TEMPLATE/log-action.yml        the "Log action" form
.github/ISSUE_TEMPLATE/discover-dismiss.yml  the "Dismiss" form on Discover
.github/ISSUE_TEMPLATE/discover-volume.yml   the "Set" form under Search volumes (Keyword Planner numbers)
.github/workflows/discover-intake.yml        applies a Dismiss or Set form within minutes, no searches
data/
  reports/<report_type>/<YYYY-MM-DD>.json   permanent archive, one file per day
  summary.json    per-video totals across 7d/28d/90d/365d/all
  daily.json      channel-level daily series
  traffic.json    traffic source breakdown
  videos.json     titles and thumbnails (refreshed, not accumulated)
  snapshots.json  public counts and change fingerprints, last 30 days only
  attention.json  what the "Needs attention" panel shows
  steam.json      Steam app per game and its recent announcements (editable)
  actions.json    every logged or detected action and its measured results
  discover.json   what Discover shows, its search budget, and per-game search terms (editable)
  baselines.json  calibrated search terms Discover measures sizes against (edited by hand, monthly)
  discover_archive/<YYYY-MM-DD>/   raw Google Trends pulls, kept since they cannot be pulled again
  state.json      which reports have been archived
```

## Dashboard

`index.html` is a static, read-only page that reads the JSON in `data/`. No
build step, no login — open it (or serve the folder) and it renders.

### Needs attention

The panel at the top watches the whole library, not just new uploads, and
compares **every video with itself**, never with a channel average, two ways.

**This week** (the last seven complete days) against last week, and against the
week before for slower climbs. A change counts only when

- it is at least **twice that video's normal week-to-week swing**, judged as a
  ratio (measured on this channel: impressions ±23%, views ±27%, CTR ±8%;
  small counts also allow for plain counting noise, so 0 → 3 never counts).
  In practice a busy video has to move about 1.6× in a week, roughly the top
  5% of weeks,
- it **survives removing the week's single biggest day**, so one random spike
  cannot trigger it, and
- the **last three days still agree**, so a burst that already faded does not.

Two weeks in a row the same way (each week clearly up on the one before) counts
as a climb or a slide even when neither step alone is dramatic.

**Shifts**: the date a video's level moved and stayed moved. Every date in the
last six months is tried as a split, the level since then against the twelve
weeks before, and the split that stands out most counts when it is about the
top 5% (roughly three times the old level for a busy video). The days after it
are searched again, so a game that rose in June and again in September reports
September. A shift stays on the panel **for as long as last week is still
clearly away from the old level**, and its card says whether it is still
rising, holding or easing off. This is what catches a game update on Sep 4
whose extra traffic is fading week on week but is still twice the summer level
in late October, which the week-on-week test alone stops seeing after a week.
Within three months of a rise, a video easing back is the wave settling, not
lost reach. Shifts start 60 days after upload, so launch decay never counts.

Rises must reach a level worth having (50 impressions or 10 views a week),
falls must start from one worth protecting (150 impressions or 25 views a
week), and CTR changes need 100 impressions in each week.

**Big enough to act on.** Real is not the same as worth an hour: 4 → 11 views a
week can be a clear change and still not matter. A card needs a change worth
at least **0.3% of the channel's weekly views** (about 23 a week at 7,600),
counting ten impressions as one view and a CTR change as the clicks it wins or
loses. The bar grows with the channel. Smaller changes are listed under
*Small changes* (folded), so nothing vanishes. The same bar applies to rising
searches and sites and to videos building up; conversation cards keep their
own minimum (5 comments a week).

What changed is grouped by what to do about it:

| Group | Means | First move |
|---|---|---|
| Fix the packaging | CTR fell while impressions rose or held | thumbnail Test & Compare, title refresh |
| Games waking up | 3+ older videos of one game moving up together, or the game's videos added up shifting with 2+ of them | ride it: new video or Short, pinned comments, playlist; cover the update behind it |
| Game updates touching your videos | a patch from the last six weeks shares a topic with an older video on the game | pin what changed, refresh the description; the update is a topic |
| Ride the wave | impressions or views clearly up, or still well above where they were before a rise | point new viewers onward: end screen, pinned comment |
| Early signals | up 3 days running; a whole game spiking on one day; same-day jumps in the public counter | look before the weekly numbers confirm it |
| Losing reach | impressions or views clearly down, or still well below where they were before a fall (also whole games cooling) | depends on the source that dropped |
| Conversation | far more comments or dislikes than last week | reply, pin an answer |
| Searches and sites on the rise | search terms, outside sites, other channels' videos sending clearly more views | the topic is heating up |
| Small changes | real changes worth under the bar (folded) | nothing yet; watch for a repeat |

Each card shows last week → this week for impressions, CTR and views (with
whether the change is clear or within the normal swing), or for a shift the
weekly level before it → last week, with a *Since* line (the best week since,
and how far it still is from the old level). The trend line covers four weeks
with last week shaded, stretched back to four weeks before a shift with the
shift date dashed. **Why** names the traffic sources and search terms,
suggesting videos or sites behind the change (for a shift, per week since it
against before), and numbered next steps name the specifics: the search term
to use, your newest video on the same game to link to and how old it is. Titles
and buttons open **YouTube Studio**; *Show in table* opens the video's full
breakdown below. Every section and group folds away, and the page remembers.

**Game updates.** For the games on the panel, and any game whose videos had 20+
views in the last four weeks, `patches.py` finds the Steam app and its
developer announcements (Steam's public store search and news feed; no key).
A card then names the update behind a change: the one closest to a shift's
date, or the latest patch since shortly before this week. Its plan says
whether any of your videos on the game covers it yet (Whiskerwood's Sep 4
shift: Patch #26, The Nautical Update, and none did). Patches whose titles
share a topic word with an older video of yours on the game ("Tax Office"
against "How To Skip Taxes") are listed under *Game updates touching your
videos*. The match is on words, so a wrong game can creep in: `data/steam.json`
holds the app chosen for each game, and an entry edited by hand with
`"manual": true` (an `appid`, or `null` for "not on Steam") is left alone.
Without network access the last saved news is used.

Games are recognised from titles ("Tropico 6: …", "How To … in Whiskerwood").
The thresholds sit at the top of `signals.py` and `monitor.py`.

### Learning loop

Notice → act → measure → remember:

1. **Act.** *✓ Did this* on a step (or *Log action* on a card) opens a
   pre-filled "Log an action" issue; submit it. Title, description, tag and
   thumbnail changes are also detected on their own from the daily
   fingerprints, without logging.
2. **Measure.** 7, 14 and 28 days later the video is compared with the same
   number of days before the action, on the metric the action targets (CTR for
   thumbnails and titles, search views for descriptions and tags, views
   otherwise), allowing for how the rest of the back catalogue moved. The
   result is posted on the issue.
3. **Remember.** Results are pooled per situation and action in *Actions and
   what worked*, and each suggested step shows how that action went before.

Issues are public, like the rest of this repository.

### Discover

What is **not** on the dashboard yet, from Google web search, worldwide. The
roadmap is in [docs/search-demand-plan.md](docs/search-demand-plan.md); the
first part is live:

**Unanswered questions in your games.** For the games you cover that still
bring views (20+ in 28 days, from your titles), Google's related searches over
the last three months are pulled from Google Trends, across all of web search
(a game reaching news or social media is a trend too; only names that are
everyday words, like *Foundation*, stay in the Games category). Every search
one of your videos already answers is dropped: when all its words appear in
one of your titles on the game, or in a YouTube search that already brings
those videos views. Piracy, shop and spec searches go too, in other languages
as well. What is left is sorted by intent (problem, how-to, news, topic) with
how much it rose (*Breakout* is more than +5000%), how big it is, the video of
yours that comes closest, and the Steam announcement a news search is about.
Other games people searched alongside are listed apart, as leads. *Dismiss*
opens a pre-filled issue; the next run hides the search and closes the issue.

**How big, not just how fast.** A rise says nothing about size: +250% can be
three people. Right after a game's searches are pulled, one more search puts
up to four of its questions beside the **baseline** on one scale: a search
term whose monthly searches are known (see *Baselines*), now *how to fish*,
~350K a month. A question's count is the baseline's times its level against
it, at the busier of its three-month average and its last week, so a fresh
problem counts at today's pace. A question too small for Trends to read
beside the baseline is under a few thousand searches a month: too small to be
worth a video, and listed as such. A question needs about
**100 searches a month** (or 1% of its game's searches until there are
counts), must be big enough for Google to chart, and must not be a one-day
spike that already faded. Searches in **another language** are a second class:
they need to be among the game's top searches (score 20+) and four times that
count. Everything under the bar is still listed under the game, as *small or
one-off* or *other languages*. *Trends* opens a question beside its game, so
one too small to chart alone still shows, as a line near zero.

**Budget.** SerpApi's free plan gives 250 searches a cycle, renewing on the
12th. `trends.py` spends at most **200** of them and leaves 50 for checks by
hand; it reads the searches left from SerpApi before spending. The top 12
games are searched every 14 days and the next 12 every 30, each with one or
two sizing searches, and the games are compared with the anchor every 30
days: six searches a run, about 86 a cycle. Without `SERPAPI_KEY` the last
results stay up.

**Editing.** In `data/discover.json`:
- `settings → games`: a game's search `term`, its `cat` (8 is Google's Games
  category, for a name that is an everyday word) or `"skip": true`, with
  `"manual": true` so the run leaves the entry alone.
- `settings → searches_per_month`: Keyword Planner's average monthly searches
  for a few of your games, worldwide. The easy way is the dashboard: *Search
  volumes* (under Discover) lists your games with **Set** next to each, which
  opens a pre-filled form. Get the number from Google Ads → Tools → Keyword
  Planner → *Get search volume and forecasts*, location *All locations*, and
  paste it as shown (a range like `10K – 100K` is fine; without ad spend that
  is all it shows, so counts are order of magnitude). The *Discover intake*
  workflow stores it within a few minutes and closes the form's issue; type
  `clear` to remove one. By hand it is e.g. `{"Snowrunner": "10K-100K"}`.
  Two or three games of different sizes work best; the one in the middle
  becomes the anchor the other games are compared with.
- `dismissed` holds what you hid.

The bar and its numbers sit at the top of `discover.py` (`MIN_MONTHLY`,
`MIN_SHARE`, `FOREIGN_TOP`, `FOREIGN_FACTOR`).

### Baselines

Google never gives search counts: Trends gives shares, and Keyword Planner
gives ranges ten times wide (100K – 1M) unless you run ads. Together they pin
a term down. `data/baselines.json` holds the result; the first entry is the
baseline every question and game is measured against, the rest are backups.
No run writes that file. Recalibrate it once a month, when Keyword Planner
has the month before (the dashboard reminds you):

1. **Pick about 8 search terms** of different sizes, mostly ones people search
   on their own (bare "witcher" is less good: Trends also counts "the witcher
   3", Keyword Planner mostly not). The baselines themselves belong in it.
2. **Google Trends:** compare them all (*Explore*, up to 8 terms), worldwide,
   all categories, web search, *Custom time range* = the whole of last month
   (e.g. 1–31 Oct). Note each term's **Average interest**.
3. **Keyword Planner:** *Get search volume and forecasts* with the same terms,
   *All locations*, *All languages*, date range = the same month. Note each
   **Avg. monthly searches** (the export's 500,000 / 5,000,000 are just the
   ranges again, not counts).
4. **Narrow:** each term's range divided by its Trends average gives the
   searches one Trends point stands for. Most terms overlap in a narrow band;
   one that does not (Trends counts it differently) is left out. That band
   times each term's average is its monthly searches, roughly ±12%.
5. **Write it down** in `data/baselines.json`: `term`, `monthly`, `low`,
   `high`, `month` ("2026-10"). Put the flattest term first.

Claude can do step 4 from screenshots of the two charts. October 2026 gave:
one Trends point ≈ 27K searches; *how to fish* ~350K (320K–400K), *wardogs*
~330K, *valheim* ~790K. With a baseline, the Keyword Planner numbers set under
*Search volumes* become a cross-check (✓ when a game's measured count fits
its range).

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

export SERPAPI_KEY=...
python discover.py --dry-run         # which games are due, what it would spend
python discover.py --max-searches 1  # one search now
python trends.py account             # searches left on the SerpApi plan
python trends.py queries "tropico 6" # one manual check (uses a search)
python trends.py compare "snowrunner" "snowrunner mods"   # two searches on one scale (uses a search)
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
| Discover says *SERPAPI_KEY is not set* | Add the secret (setup step 3); the last results stay up meanwhile |
| Discover says *too little Google data* for a game | Give it a better `term` (or `cat`) under `settings → games` in `data/discover.json`, with `"manual": true` |
| Discover shows shares, not searches a month | Add a baseline to `data/baselines.json` (*Baselines*); or press **Set** under *Search volumes* for two or three games and paste Keyword Planner's numbers |
| Discover says it is time to recalibrate | Last month's Keyword Planner numbers are out: redo *Baselines* steps 1–5 and update `data/baselines.json` |
| A Set or Dismiss form changed nothing | The *Discover intake* workflow applies it within minutes (Actions tab); a form it cannot read is closed with a comment saying why |

## Data retention

The YouTube API Services Developer Policies require stored resource metadata
(titles, thumbnails) to be refreshed or deleted after 30 days, so `videos.json`
is **rewritten** each run rather than accumulated. For the same reason
`snapshots.json` keeps each video's public view, like and comment counts, and
its title with fingerprints (hashes, not text) of the description, tags and
thumbnail, for the last 30 days only. `actions.json` keeps only what was done,
when, and the measured numbers. The aggregate metrics in
`data/reports/` are not resource metadata and are kept indefinitely — that is
the entire point.
