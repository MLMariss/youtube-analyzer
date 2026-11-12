# Discovery from Google search demand — project plan

Status: **Phase 1 built** (12 Nov 2026), waiting for its first live searches.
Phases 2–6 planned. Each phase below
has a checklist; tick items as they ship so this file stays the source of truth.

## Goal

Show **what is not on your dashboard**:
- unanswered questions about games you cover
- new games rising in your genres
- areas heating up

The dashboard already covers how your own videos and games perform, through
impressions, CTR, views and shifts. This adds **what you haven't touched
yet**, measured on **Google web search**, where interest in games and problem
topics surfaces first.

## Decisions so far

| Topic | Decision |
|---|---|
| What's measured | **Google web search**, worldwide. Not YouTube search. |
| Focus | **Discovery only.** No demand board for games you already cover: your dashboard shows those through your own data. |
| Build order | 1. Unanswered questions → 2. New games radar → 3. Areas heating up |
| Radar breadth | Your genres (city builders & colony sims, survival & base building, tactics & strategy) **plus neighbours** (factory, automation, management) |
| Data source now | **SerpApi free tier**: 250 searches per cycle (renews on the 12th), 250/hour. Free only. |
| Long-term | **Official Google Trends API.** Apply for the alpha now. It covers web search, so it can replace SerpApi cleanly later. |
| Budget | Automation capped at **200 searches/month**. **50 a month stay free** for your manual checks. |
| Geography | Worldwide now. Americas / Europe / Asia / All later, with the official API. |
| "Market or me" | **Second grade**, built only after discovery works |
| Where it shows | A new foldable **Discover** section on `index.html`, below *Needs attention* |

**Changed from the first draft:**
- YouTube-search Trends → web search.
- The demand board for your games was dropped.
- "Market or me" was moved to later.
- Discovery is now the core.

## How "not on your dashboard" is decided

Everything that surfaces passes one filter. An item is dropped if it is
**already yours**:

- **Games you cover:** the games `monitor.game_names` finds in your titles,
  plus the apps in `data/steam.json`, plus manual entries.
- **Topics you cover:** queries sharing a topic word with your titles on that
  game. This reuses `patches.topic_words` / `covered_by`, the matcher that
  already pairs "Tax Office" with "How To Skip Taxes".
- **Searches that already bring you views:** the YouTube search terms in
  `channel_traffic_source_a3` (`monitor.load_sources`). If people already find
  you with it, it isn't unexplored.
- **Dismissed items:** your *Dismiss* button removes an item for good.
  *Track* moves a game onto your watchlist.

Each item keeps a **first seen** date (the `monitor.carry_first_seen` pattern),
so the section shows *new this run* separately from *still rising*.

## Sources

| Source | Used for | Cost |
|---|---|---|
| **SerpApi Google Trends**, web, worldwide | `RELATED_QUERIES` (top and rising questions), `RELATED_TOPICS` (rising entities: games), `TIMESERIES` (sizing, up to 5 terms per search). Rising values are a % or *Breakout*. | 1 search per call, from the 200 cap |
| **Steam store** (public, no key; `patches.py` already uses it) | New releases, coming soon, top sellers, tags and genres, release dates, store links | Free |
| **Steam stats** (public, no key) | Current players, review counts: momentum for candidates | Free |
| **YouTube Data API**, using your existing token's `youtube.readonly` scope | How many recent videos other channels made on a candidate: the competition (Phase 4) | 100 units per search, out of 10,000 a day |
| Google autocomplete (optional) | Problem phrasing ("tropico 6 can't …"). The public suggest endpoint is unofficial; SerpApi's autocomplete engine costs searches. | Free / 1 search |

---

## Phase 0: Setup (you, about 15 minutes)

- [x] Create a free SerpApi account. Confirmed 12 Nov 2026: Free Plan, **250 searches
  per cycle, renewing on the 12th** (next 12 Dec 2026), rate limit 250/hour.
- [x] Add the repo secret **`SERPAPI_KEY`**.
- [ ] Apply for the **Google Trends API alpha** at
  developers.google.com/search/apis/trends. Use case: *finding rising game
  topics for a creator channel*.
- [ ] Optional: allow `serpapi.com` in this cloud environment so I can test
  from here. Otherwise testing runs through a workflow dispatch.
- [ ] My first calls check five things:
  - the games category id for `cat`
  - the topic "type" field in `RELATED_TOPICS`
  - that SerpApi's account endpoint is free
  - which Steam endpoint lists games by tag

## Phase 1: Unanswered questions in your games (about 40 searches/month)

**Goal:** rising Google searches about games you already cover that none of
your videos answers, e.g. *"tropico 6 crash on startup"* or *"how to stop
rebels"*. Your audience already finds you for these games, so these are the
cheapest wins.

**Pull:**
- `RELATED_QUERIES`, web, worldwide, `today 3-m`, one game per search.
- Your **top 12 games by views** every 2 weeks (about 26 searches) and the
  **next 12** monthly (about 12). The game list is `monitor.py`'s watched set,
  minus `skip` entries.
- Each game can get a better term in `data/discover.json` (a plain word like
  "Foundation" needs the games category).

**Keep:**
- rising queries (Breakout first), and top queries none of your titles cover
- minus filler (download, free, price, system requirements, release date,
  crack)
- minus what's already yours (see the filter above)

**Sorted by intent:**
- **Problem** (crash, fix, error, not working, stuck, can't)
- **How-to** (how to, best, guide, layout, build, tips)
- **News** (update, patch, DLC, 1.0). These get linked to the Steam patch from
  `patches.py` when one matches.

**Card**, for example:
> *Tropico 6 — rising on Google: "tropico 6 rebels" +250%, "crash on startup"
> Breakout. None of your 70 Tropico 6 videos covers these. Closest: "How to …"
> (add it to the description or pin an answer), or make a new video.*

Each card links to the Google results and the Trends page for the query, and
has *Dismiss*.

**Done when:**
- [x] `trends.py` exists: the SerpApi provider, budget ledger (by SerpApi's
  cycle) and key redaction. Each game's latest pull is kept in
  `data/discover.json`, so no search is repeated before it is due.
- [x] `discover.py` exists with the filter and this stream.
- [x] `data/discover.json` is written, and the raw pulls go to
  `data/discover_archive/<date>/`, excluded from Pages. It isn't
  `data/discover/`: Jekyll excludes by path prefix, which would also have
  hidden `data/discover.json`.
- [x] The Discover section is on the dashboard, with Dismiss through
  `.github/ISSUE_TEMPLATE/discover-dismiss.yml`.
- [x] The workflow step and secret are in, and the README section is written.
- [ ] Verified:
  - [x] `--dry-run` (games, searches it would spend)
  - [ ] `--max-searches 2` live, with queries checked against trends.google.com
  - [x] an offline run, and one with a missing key, still builds the dashboard
  - [x] screenshots at phone and desktop width

## Phase 2: New games radar (about 40 searches/month)

**Goal:** games rising on Google in your genres and neighbours that you've
never covered.

**Candidates:**
- **Rising topics:** `RELATED_TOPICS`, web, worldwide, `today 1-m`, games
  category, every 2 weeks.
  - Editable seed terms: "city builder", "colony sim", "survival game", "base
    building", "strategy game", "tactics game".
  - Neighbour seeds: "factory game", "automation game", "management game".
  - That is about 20 searches a month. Only topics typed as video games are
    kept.
- **Steam lists** (free): new releases, coming soon and top sellers carrying
  matching Steam tags (City Builder, Colony Sim, Survival, Base Building,
  Strategy, Tactics, Automation, Management).

**Filter:** not one of your games, not dismissed. Matched to Steam with
`patches.find_app` for its tags, release date and store link.

**Sizing:**
- `TIMESERIES` `today 3-m`, web, worldwide, **4 candidates + 1 yardstick
  game** per search, about 20 searches a month.
- The yardstick is one familiar game you cover, default Tropico 6, editable.
  It makes a new candidate's size readable, e.g. *searched 0.6× Tropico 6 and
  up 80% in a month*. Shortlisted games are re-sized weekly in the same
  batches.

**Ranked by** demand (× yardstick) × momentum (90-day trend) × fit (Steam tags
shared with your best-performing games).

**Card:**
- name, Steam link, released or upcoming date, tags
- **why it surfaced** (rising for "colony sim" +400% / Steam coming soon)
- size × yardstick and a 90-day line
- **Track** / **Dismiss** buttons. Each opens a pre-filled issue, like
  *Log action*. The daily run reads them the way `actions.py` reads "Action:"
  issues.
- Tracked games get their Steam patches followed. Once you upload a video on
  one, `game_names` sees it and it leaves the radar on its own.

**Done when:**
- [ ] Seeds, Steam candidates, sizing, ranking and the cards ship.
- [ ] A *Track* form joins `discover-dismiss.yml` (Phase 1), and the run reads
  it.

## Phase 3: Areas heating up (about 20 searches/month)

**Goal:** directions, not single games: themes and sub-genres gaining
interest, e.g. *"cozy city builder"*, *"medieval colony sim"* or *"co-op base
building"*.

**Pull:**
- `RELATED_QUERIES` for the same seeds every 2 weeks (about 18 searches).
- Plus a monthly `TIMESERIES` of the seeds themselves (5 per search), to see
  which genre is growing overall (about 2 searches).

**Grouped** into themes by shared topic words. Each theme shows its rise and
**example games** taken from the Phase 2 candidates with matching tags.

**Growing reach:** an area that keeps rising for 3 runs is offered as a new
seed, with a button. You approve it, so the radar widens with you.

**Done when:**
- [ ] Themes, genre trend line and the seed suggestions ship.

## Phase 4: Smarter discovery (mostly free)

- **Steam momentum:** week-on-week current players and review counts for
  candidates. This confirms a Trends rise with real players.
- **Competition:** recent YouTube videos on a candidate or query, and their
  views, via the Data API. *High search, few videos* is the opportunity
  score. Only counts are stored: API policy bars keeping other channels'
  metadata past 30 days.
- **Memory:** when a new upload matches a discovery item, its first 28 days
  are compared with your median new video. *Discoveries that paid off* then
  feed the ranking, the way `actions.py` builds its playbook.

## Phase 5: Second grade, "market or me" (about 25 searches/month, from headroom)

- *Needs attention* cards about a game get one line saying whether Google
  searches for that game moved too:
  - searches up with you: the game is waking up
  - searches flat: YouTube is pushing your videos
  - searches down with you: the game is cooling, so don't touch thumbnails
- A *Demand rising, you're not there* group for games you cover whose
  searches clearly rose while your videos didn't.
- Steam update lines gain the search reaction.

## Phase 6: Official API, continents, extras

- **Official Google Trends API provider** (`trends.py` swaps providers). Its
  consistent scaling removes the yardstick and batch juggling.
- **Continents: All / Americas / Europe / Asia.** Country data rolled up,
  weighted by **where your viewers are** (Europe 45%, Americas 36%, Asia
  13.5%, from `channel_basic_a3`). A selector on the Discover section.
- **Wording check:** `python trends.py compare "tropico 6 tips" "tropico 6
  guide"`, using the manual budget.

---

## Budget (SerpApi free tier)

| Stream | Searches/month |
|---|---|
| 1 Unanswered questions | ~40 |
| 2 New games radar (topics ~20, sizing ~20) | ~40 |
| 3 Areas heating up | ~20 |
| 5 Market or me (later) | ~25 |
| Headroom: retries, growth | ~75 |
| **Automation cap** | **200** |
| Your manual checks | 50 |

**Enforcement:**
- The 200 cap follows SerpApi's cycle, which runs from the 12th to the 12th,
  not the calendar month.
- Before spending, the run reads the searches left from SerpApi's account
  endpoint. A local ledger in `data/discover.json` is the backup.
- Near the cap, things are dropped in this order: Phase 5, then Phase 3, then
  Phase 2 sizing refreshes.
- **If the cap is ever tighter** (searches used elsewhere, or SerpApi cuts the
  free tier), the lean profile:
  - Phase 1 monthly for the top 12: ~12
  - Phase 2 monthly: ~18
  - Phase 3 monthly: ~10

## How it fits the repo

The repo's rules stay:
- Standard library only.
- A failure never blocks the daily commit.
- Without network, the last saved data is used.
- Hand edits with `"manual": true` are kept.
- Thresholds sit at the top of the module.
- The dashboard explains how to read the numbers.

| Piece | What |
|---|---|
| `trends.py` (new) | Provider (SerpApi now, official later), budget ledger, caching, redacting the key from every log and error |
| `discover.py` (new) | The filter, the three streams, ranking, Track/Dismiss from issues |
| `data/discover.json` (new) | **Editable:** seeds, yardstick, per-game term/skip. **Generated:** items with first seen, rise, sizing, Steam match, budget used. |
| `data/discover_archive/<date>/` | Raw rising lists (point-in-time, can't be re-pulled). Excluded from Pages in `_config.yml`. |
| `.github/workflows/collect.yml` | **Discover** step after *Find videos that need attention*. `continue-on-error`, `SERPAPI_KEY` + `GITHUB_TOKEN`, dispatch input `discover_force`. Summary shows searches used and left. The daily cron stays; `discover.py` decides what is due. |
| `.github/ISSUE_TEMPLATE/discover-dismiss.yml` | Dismiss form (Phase 1); a Track form follows in Phase 2 |
| `index.html` | **Discover** section with *Unanswered questions*, *New games*, *Areas heating up*, and a "How to read this" box |
| `README.md` | Link to this plan now; a section when Phase 1 ships |

Reused:
- `monitor.game_names`, `game_of`, `load_sources` and `carry_first_seen`
- `patches.topic_words`, `covered_by` and `find_app`, plus `data/steam.json`
- `actions.github` (issues)
- `summarize.write_json`

## Limitations (also written into "How to read this")

- **Relative, not volume.** Trends gives a 0–100 index or a % rise, never
  counts. A +300% on a tiny query can be a handful of searches; *Breakout*
  means more than +5000%.
- **Worldwide mixes languages.** Rising lists can include German or Polish
  phrasing. It's still signal, but it needs reading.
- **Rising lists are noisy:** piracy, prices, "release date", mainstream
  games. Filler lists and the genre filter help; you still pick.
- **Ambiguous names** (Foundation, Grounded, Icarus) need the games category
  filter or a better term.
- **Free tier is shared:** SerpApi used for anything else eats the same
  allowance.
- **Unofficial endpoints** (Steam store lists, Google suggest) can change.
  Each is optional and fails quietly.
- **Public repo:** discovery lists end up on the public Pages site. Check
  SerpApi's terms; the fallback is a private summary.
- **Personal accounts only:** never a colleague's or a company's keys.
- **The API key travels in the URL:** it is redacted from every log.

## Reference

- Google Trends API alpha (developers.google.com/search/apis/trends) and launch
  post (developers.google.com/search/blog/2025/07/trends-api)
- SerpApi Google Trends (serpapi.com/google-trends-api), related queries and
  related topics pages, pricing (serpapi.com/pricing)
- DataForSEO Google Trends (what the colleague's tool uses; paid): fallback if
  free tiers prove too small
- Tester notes on the alpha quota (willmanntobias.medium.com)
