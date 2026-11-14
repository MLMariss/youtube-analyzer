# Discovery from Google search demand — project plan

Status (14 Nov 2026): **Discover is about games you have not touched.**
- Phase 2 (new games radar), Phase 3 (areas heating up) and the Steam
  momentum and YouTube competition parts of Phase 4 are built. They wait for
  their first live run.
- Phase 1 (questions about games you already cover) is built but **paused**:
  your own video data tracks those games.
- Phase 5 is **on demand only**.
- Phase 6 is planned.

Each phase below has a checklist; tick items as they ship so this file stays
the source of truth.

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
| Focus | **Discovery only, of games you have not touched.** No Google searches are spent on games you cover: your dashboard tracks those through your own data (14 Nov 2026: Phase 1 paused, `settings → your_games → search`). |
| New vs established | The radar leads with **new & upcoming** games (out in the last 12 months, or not out yet). Older games you never covered are listed apart, folded. |
| One game, one card | A game is one card however people search it: Google *topics* identify games, and the searches naming a game ("valheim tips", "valheim map") are listed on its card. |
| Build order | 1. Unanswered questions → 2. New games radar → 3. Areas heating up |
| Radar breadth | Your genres (city builders & colony sims, survival & base building, tactics & strategy) **plus neighbours** (factory, automation, management) |
| Data source now | **SerpApi free tier**: 250 searches per cycle (renews on the 12th), 250/hour. Free only. |
| Long-term | **Official Google Trends API.** Apply for the alpha now. It covers web search, so it can replace SerpApi cleanly later. |
| Budget | Automation capped at **200 searches/month**. **50 a month stay free** for your manual checks. |
| Geography | Worldwide now. Americas / Europe / Asia / All later, with the official API. |
| "Market or me" | **On demand only** (14 Nov 2026): a *Check Google* link on Needs attention cards opens the game's searches beside the baseline. No automatic searches on your games. |
| Noise | **A rise is not a size.** Every item must be big enough to act on, not just real. Below the bar it is listed apart (*small or one-off*), never dropped silently. The same rule runs the whole dashboard: a *Needs attention* card needs a change worth 0.3% of the channel's weekly views. |
| Sizes | Each question is measured against a **baseline** on one Trends scale: a search term whose monthly searches are pinned down (now *how to fish*, ~350K, Oct 2026). Too small to read beside it means too small to be worth a video. |
| Baseline | Calibrated by hand monthly: ~8 terms compared in Trends and Keyword Planner for the same month; their 10×-wide ranges overlap in a ±12% band (README → Baselines). Kept in `data/baselines.json`. Keyword Planner numbers set per game are a cross-check. Automating the monthly calibration comes later. |
| Scope | **All of web search**, not the Games category: a game reaching news, social media or business pages is a trend too. Only names that are everyday words (Foundation, Grounded, Icarus, Odyssey, Humankind, Windrose) stay in the Games category. |
| Other languages | **A second class with a higher bar:** among the game's top searches at a score of 20+, and 4× the English count. The rest are listed apart. |
| Where it shows | A new foldable **Discover** section on `index.html`, below *Needs attention*: New games in your genres, Areas heating up, then the paused questions and Search volumes, folded |

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
  (14 Nov 2026: a personal *youtube-analyzer* cloud environment allows
  `store.steampowered.com` and `api.steampowered.com`; SerpApi parts were
  tested against mocked responses.)
- [ ] My first calls check five things:
  - [x] the games category id for `cat` (8)
  - [ ] the topic "type" field in `RELATED_TOPICS` (the radar keeps types
    with "game" in them, not genre, series or company: check on the first run)
  - [x] that SerpApi's account endpoint is free
  - [x] which Steam endpoint lists games by tag:
    `store.steampowered.com/search/results/?tags=<id>&filter=popularnew|topsellers|popularcomingsoon&category1=998&infinite=1`.
    It returns HTML rows with app id, name, release date, review count and
    the top 7 tag ids. Tag ids come from `/tagdata/populartags/english`.

## Phase 1: Unanswered questions in your games (paused, 14 Nov 2026)

**Paused** by default (`settings → your_games → search: false`): no searches
are spent on games you cover. The last results are rebuilt from the saved
pulls and shown, folded. Set it to `true` to resume (~86 searches a cycle).

**Goal:** rising Google searches about games you already cover that none of
your videos answers, e.g. *"tropico 6 crash on startup"* or *"how to stop
rebels"*. Your audience already finds you for these games, so these are the
cheapest wins.

**Pull:**
- `RELATED_QUERIES`, web (all categories), worldwide, `today 3-m`, one game
  per search. Games whose name is an everyday word stay in the Games category.
- Your **top 12 games by views** every 2 weeks (about 26 searches) and the
  **next 12** monthly (about 12). The game list is `monitor.py`'s watched set,
  minus `skip` entries.
- Each game can get a better term in `data/discover.json` (a plain word like
  "Foundation" needs the games category).

**Keep:**
- rising queries, and top queries none of your titles cover
- minus filler (download, free, price, system requirements, release date,
  crack), in other languages too (скачать, купить, descargar, kaufen)
- minus what's already yours (see the filter above)

**Size** (added 13 Nov 2026, after the first live check: *snowrunner mod
installer* showed as Breakout, and Google Trends had too little data to chart
it at all):
- Right after a pull, one `TIMESERIES` search puts the game and up to 4 rising
  questions on one scale (a second search for more; the game's top search is
  the reference that sizes the top list). About 40 searches a month.
- A question's level is the busier of its 90-day average and its last week,
  so a problem that started days ago counts at today's pace.
- **Counts:** Keyword Planner's monthly searches for one or more games, set
  from the dashboard (*Search volumes* → **Set**, a pre-filled issue that the
  *Discover intake* workflow applies within minutes) or by hand under
  `settings → searches_per_month` (a number or a range like "10K-100K"). The game in the middle is the anchor; every 30 days the other
  games are compared with it, 4 to a search, 2 searches a run, first. About 8
  searches a month. A count is the game's count times the question's share.

**The bar** (provisional, tune after a cycle of sizes):
- big enough to chart (level 0.5+ on the shared scale), and not a one-day
  spike that already faded
- ~100+ searches a month with counts, or 1%+ of the game's searches without
- other languages: a top score of 20+, and 4× that count or share
- everything under the bar is listed per game as *small or one-off* or
  *other languages*

**Sorted by intent:**
- **Problem** (crash, fix, error, not working, stuck, can't)
- **How-to** (how to, best, guide, layout, build, tips)
- **News** (update, patch, DLC, 1.0). These get linked to the Steam patch from
  `patches.py` when one matches.

**Card**, for example:
> *Tropico 6 — rising on Google: "tropico 6 rebels" +250%, "crash on startup"
> Breakout. None of your 70 Tropico 6 videos covers these. Closest: "How to …"
> (add it to the description or pin an answer), or make a new video.*

Each card links to the Google results and the Trends page for the query
(beside its game, so a search too small to chart alone still shows), and has
*Dismiss*.

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
- [x] Sizes, the bar, web-wide scope and other languages (13 Nov 2026), tested
  against mocked SerpApi responses
- [x] *Search volumes* panel with a **Set** form per game, applied within
  minutes by `.github/workflows/discover-intake.yml` (Dismiss too)
- [x] Baselines (`data/baselines.json`): questions and games measured against a
  calibrated term; October 2026 calibrated by hand (how to fish ~350K)
- [ ] Monthly calibration automated (8 terms in Trends against Keyword Planner)
- [ ] Keyword Planner numbers entered for 2-3 games (a big, a middle and a
  small one), worldwide
- [ ] The bar tuned after the first cycle of sizes
- [ ] Verified:
  - [x] `--dry-run` (games, searches it would spend)
  - [ ] `--max-searches 2` live, with queries checked against trends.google.com
  - [x] an offline run, and one with a missing key, still builds the dashboard
  - [x] screenshots at phone and desktop width

## Phase 2: New games radar (about 60 searches/month with Phase 3)

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

**As built** (14 Nov 2026, `radar.py`):
- **Candidates:**
  - Steam's *New & Trending*, *Top Sellers* and *Popular Upcoming* lists for
    nine tags, every run, free. The search results page gives each game's top
    seven tags and its review count.
  - `RELATED_TOPICS` for nine seeds, Games category, `today 1-m`, every 14
    days. Topics typed as a game are kept (not genres, series or companies).
- **Not yours:**
  - Left out: games in your titles, games any title names (even once), your
    Steam apps, and anything dismissed.
  - Kept: sequels to your games, marked.
- **Fit:** the share of your views on games with the same Steam tags (top 24
  games by views), not a fixed yardstick game.
- **Sizing:**
  - The shortlist is 12 new and 4 established games by a first guess, from
    reviews and why each surfaced.
  - Each game is measured as its **Google topic** against the baseline, not a
    yardstick game, 4 to a search, every 14 days. A topic is found once with
    Trends autocomplete (1 search) and kept.
- **Momentum:**
  - Google: the last 4 weeks against the first 4 of the 90 days.
  - Steam: players at the daily check against a week ago, and reviews in the
    last week.
- **Ranking:** log(searches a month) × momentum (×0.5–×3) × (0.5 + fit).
- **New vs established:** out in the last 12 months or upcoming leads; older
  games are folded below.
- **One card per game:** the seeds' related queries naming a game are listed
  on its card.

**Done when:**
- [x] Seeds, Steam candidates, sizing, ranking and the cards ship.
- [x] Dismiss (`discover-dismiss.yml` with game `new games`).
- [ ] A *Track* form, and tracked games' Steam patches followed.
- [ ] First live run checked: topic types, autocomplete matches, sizes
  against trends.google.com.

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

**As built** (14 Nov 2026):
- **Themes:** the seeds' `RELATED_QUERIES` (pulled with the topics) that name
  no game, grouped by the most shared word beyond every genre word. A theme
  needs a rising search, and its Steam tag (Cozy, Medieval, Co-op…) gives
  example games.
- **Seeds:** a theme rising in 3 pulls is highlighted with *Add as seed*.
  That button is on every theme, and opens `discover-seed.yml`, which the
  intake applies within minutes.
- **Genre trend:** the seeds against the baseline monthly, 4 to a search.

**Done when:**
- [x] Themes, genre trend line and the seed suggestions ship.

## Phase 4: Smarter discovery (mostly free)

- [x] **Steam momentum:** week-on-week current players and review counts for
  candidates. This confirms a Trends rise with real players. Built 14 Nov
  2026: the top 25 radar games, every run, from `GetNumberOfCurrentPlayers`
  and `appdetails` (recommendations). Steam's `appreviews` endpoint redirects,
  so it is not used.
- [x] **Competition:** recent YouTube videos on a candidate or query, and their
  views, via the Data API. *High search, few videos* is the opportunity
  score. Only counts are stored: API policy bars keeping other channels'
  metadata past 30 days. Built 14 Nov 2026:
  - the top 12 radar games, weekly, 101 quota units each
  - *Few videos* = 2,000+ searches a month and under 10 videos in 30 days
    (provisional)
  - counts older than 30 days are deleted
- **Memory:** when a new upload matches a discovery item, its first 28 days
  are compared with your median new video. *Discoveries that paid off* then
  feed the ranking, the way `actions.py` builds its playbook.

## Phase 5: Second grade, "market or me" (on demand only, 14 Nov 2026)

**Decided:** no automatic searches on games you cover. *Check Google* on Needs
attention cards (game cards, and video cards on a game) opens the game's
searches beside the baseline on Google Trends, for free. The ideas below stay
for if that is not enough.

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
| 1 Unanswered questions (paused; ~86 when on) | 0 |
| 2+3 Seeds: topics and queries, 9 seeds every 14 days | ~40 |
| 2 Topics found (autocomplete, once per game) and sizing | ~20 |
| 3 Genres measured monthly | ~3 |
| 5 Market or me (on demand, free links) | 0 |
| Headroom: more seeds, retries, Phase 1 if turned on | ~137 |
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
| `discover.py` (new) | Phase 1 (paused), Dismiss / Set / Seed forms from issues, runs the radar, writes `discover.json` |
| `radar.py` (new, 14 Nov 2026) | Phases 2 and 3 and Phase 4's Steam momentum and YouTube competition |
| `data/discover.json` (new) | **Editable:** `settings → radar` (seeds, steam_tags), `settings → your_games`, per-game term/skip. **Generated:** the radar, the themes, the questions, budget used. |
| `data/radar_state.json` (new) | What the radar's next run needs: Steam lists, seed pulls, Steam lookups, Google topics, sizes, player and review histories, YouTube counts (deleted after 30 days) |
| `data/discover_archive/<date>/` | Raw rising lists (point-in-time, can't be re-pulled). Excluded from Pages in `_config.yml`. |
| `.github/workflows/collect.yml` | **Discover** step after *Find videos that need attention*. `continue-on-error`, `SERPAPI_KEY` + `GITHUB_TOKEN`, dispatch input `discover_force`. Summary shows searches used and left. The daily cron stays; `discover.py` decides what is due. |
| `.github/ISSUE_TEMPLATE/discover-dismiss.yml` | Dismiss form (a question, a radar game, a theme); a Track form follows |
| `.github/ISSUE_TEMPLATE/discover-seed.yml` | *Add as seed* form (Phase 3) |
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
  means more than +5000%. Sizes come from comparing a question with its game,
  and counts from Keyword Planner numbers entered by hand: order of magnitude.
  Without ad spend Keyword Planner gives ranges (10K–100K); its numbers are
  12-month averages, Trends' are the last 90 days.
- **Resolution.** Trends rounds to whole points of the busiest term, so a
  question under about 1% of its game's searches reads as zero: *too small to
  chart*.
- **Worldwide mixes languages.** Rising lists include Hungarian, Russian or
  Polish phrasing. They are a second class with a higher bar; the word list
  that spots plain-letter ones (`FOREIGN_WORDS`) grows as they turn up.
- **Rising lists are noisy:** piracy, prices, "release date", mainstream
  games. Filler lists and the genre filter help; you still pick.
- **Ambiguous names** (Foundation, Grounded, Icarus) need the games category
  filter or a better term. Their counts are approximate: they are compared
  with the anchor inside the Games category.
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
