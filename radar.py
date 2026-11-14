#!/usr/bin/env python3
"""
Discover, parts 2 and 3: games you have not touched yet, and the areas around
them heating up. discover.py runs this; the roadmap is in
docs/search-demand-plan.md.

New games in your genres
------------------------
Every game here is one you have never made a video on: not in your titles
(monitor.game_names), not one of your Steam apps (data/steam.json), not
dismissed. Candidates come from two places:

    Steam, free, every run: the New & Trending, Top Sellers and Popular
        Upcoming lists of your genre tags (settings -> radar -> steam_tags).
    Google Trends, every SEED_EVERY days: the related topics of genre seeds
        (settings -> radar -> seeds: "colony sim", "survival game"...), Games
        category, last month. A topic is an entity, so a game is one entry
        however people type it. The seeds' related queries that name a game
        ("valheim tips", "valheim map") are listed under that game, not as
        rows of their own.

Each game gets:
    fit         Steam tags it shares with the games that bring you views,
                weighted by those views (0-1).
    size        searches a month, measured as its Google topic against the
                baseline (data/baselines.json), 90 days, four to a search;
                the topic is found once with Trends' autocomplete and kept.
                Only the SHORTLIST best by a first guess are measured
                (twelve new, four established).
    momentum    Google: its last four weeks against its first four, 90 days
                back. Steam: players now against a week ago, and reviews
                written in the last week.
    competition videos other channels uploaded on it in the last 30 days
                (YouTube search; only counts are kept, never the videos).
Ranked by log10(searches a month) x momentum x (0.5 + fit); games not
measured yet come after, by the first guess. Games out in the last
NEW_FOR_DAYS days or not out yet are "new & upcoming" and lead; older games
you never covered are "established" and listed apart.

Areas heating up
----------------
The seeds' related queries that name no game ("cozy city builder", "co-op
base building") are grouped into themes by the word they share beyond the
seed. A theme with a rising query is heating up; one that kept rising over
SUGGEST_ROUNDS pulls is offered as a new seed. Once a month the seeds
themselves are measured against the baseline: which genre grows overall.

Budget: the seeds take two searches each per pull (topics, queries), about
40 a cycle; finding topics and sizes about 20 more; genres 3. Steam and the
YouTube counts cost no Google Trends searches.

State that only the next run needs (raw pulls, Steam lists, histories) is in
data/radar_state.json; the dashboard reads the result from data/discover.json.
"""

import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trends
from discover import FOREIGN_WORDS, JUNK, MIN_POINTS, PLATFORM, archive, iso, load_json, mean, size_of, slug, words
from monitor import SEQUEL, game_of
from summarize import DATA_DIR, write_json

STATE_PATH = os.path.join(DATA_DIR, "radar_state.json")

# What to look at. Both lists are copied into settings -> radar in
# data/discover.json on the first run; edit them there.
SEEDS = ["city builder", "colony sim", "survival game", "base building game", "strategy game",
         "tactics game", "factory game", "automation game", "management game"]
STEAM_TAGS = ["City Builder", "Colony Sim", "Survival", "Base Building", "Strategy", "Turn-Based Tactics",
              "Automation", "Management", "Open World Survival Craft"]

SEED_EVERY = 14         # days between a seed's pulls
SEED_RANGE = "today 1-m"
SIZE_RANGE = "today 3-m"
NEW_FOR_DAYS = 365      # released this recently, or not out yet: "new & upcoming"; older is "established"
SHORTLIST = (12, 4)     # games measured on Google, the best by the first guess: (new, established)
SIZE_EVERY = 14         # days before a game is measured again
RESOLVE_RUN = 2         # Trends autocomplete searches per run (finding a game's topic)
SIZE_RUN = 2            # sizing searches per run, four games each
TOPIC_RETRY = 60        # days before a game with no Google topic is looked up again
GENRES_EVERY = 30       # days between measuring the seeds themselves
KEEP = (30, 15)         # games written for the dashboard: (new, established)
SEARCHES_PER_GAME = 6   # searches listed under a game

STEAM_COUNT = 25        # games per Steam list
UPCOMING_COUNT = 15
LOOKUP_EVERY = 30       # days before a Steam lookup (tags, reviews) is repeated
LOOKUPS_RUN = 60        # Steam lookups per run
STEAM_PAUSE = 0.25      # seconds between Steam requests
MOMENTUM_GAMES = (20, 5)  # games whose players and reviews are read every run: (new, established)
HISTORY_DAYS = 21

COMPETITION_GAMES = (10, 2)  # games whose YouTube competition is counted: (new, established)
COMPETITION_EVERY = 7
COMPETITION_DAYS = 30
FEW_VIDEOS = 10         # "few videos": under this many in 30 days...
FEW_MIN_MONTHLY = 2000  # ...on a game searched at least this much a month. Provisional.

SUGGEST_ROUNDS = 3      # pulls, SEED_EVERY apart, a theme must keep rising in to be offered as a seed
NEW_DAYS = 7

STORE = "https://store.steampowered.com"
TAGS_URL = STORE + "/tagdata/populartags/english"
SEARCH_URL = STORE + "/search/results/?{}"
DETAILS_URL = STORE + "/api/appdetails?appids={}&filters=recommendations,release_date"
PLAYERS_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={}"
DATA_API = "https://www.googleapis.com/youtube/v3"
USER_AGENT = "mlmariss-youtube-analyzer"
LISTS = {"trending": ("New & Trending", {"filter": "popularnew"}, STEAM_COUNT),
         "top": ("Top Sellers", {"filter": "topsellers"}, STEAM_COUNT),
         "upcoming": ("Popular Upcoming", {"filter": "popularcomingsoon"}, UPCOMING_COUNT)}

# Google's topic types: a game, not a genre, a series or a company.
GAME_TYPE = re.compile(r"\bgames?\b", re.I)
NOT_GAME_TYPE = re.compile(r"genre|series|franchise|developer|publisher|company|studio|engine|console|platform|"
                           r"board|card|tabletop|sport|character|store|award|esport|tournament|streamer|youtuber|"
                           r"website|magazine|convention|expo|festival|software|\bmod\b", re.I)
# Words that make no theme on their own: "best colony sim", "city builder simulator".
GENERIC = {"best", "new", "top", "good", "free", "upcoming", "like", "similar", "list", "play", "sim", "simulator",
           "simulation", "type", "kind", "genre", "recommendation", "recommend", "fun", "popular", "big", "small",
           "old", "classic", "latest", "release", "released", "coming"}


# ------------------------------------------------------------------ text

def norm(name):
    """Lower case, no marks or punctuation: "Anno 117: Pax Romana™" -> "anno 117 pax romana"."""
    n = html.unescape(str(name or "")).lower()
    n = re.sub(r"[™®©]", "", n)
    n = re.sub(r"[^\w\s']+", " ", n).replace("_", " ")
    return re.sub(r"\s+", " ", n).strip()


def head_of(name):
    """
    The name people search, without its subtitle or edition, when what is
    left still says which game: "Anno 117: Pax Romana" -> "Anno 117", but
    "Cities: Skylines II" and "Dune: Awakening" stay whole ("Cities" is any city).
    """
    full = re.sub(r"[™®©]", "", html.unescape(str(name or ""))).strip()
    head = re.split(r"\s*[:–—|]\s*|\s+-\s+", full)[0].strip()
    return head if head and (len(head.split()) >= 2 or len(head) >= 7) else full


def short(name):
    """head_of() for matching: "anno 117"."""
    return norm(head_of(name)) or norm(name)


def display_short(name):
    return head_of(name) or str(name)


def base_of(key):
    """A game's name without its sequel number: "tropico 6" -> "tropico"."""
    parts = key.split()
    return " ".join(parts[:-1]) if len(parts) > 1 and SEQUEL.match(parts[-1]) else key


def mentions(text, name):
    return bool(name) and re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", text) is not None


def foreign(text):
    """A search in another language: letters English does not use, or a word in discover.FOREIGN_WORDS."""
    return not text.isascii() or any(w in FOREIGN_WORDS for w in re.findall(r"\w+", text))


def is_game_topic(t):
    kind = t.get("type") or ""
    return bool(GAME_TYPE.search(kind)) and not NOT_GAME_TYPE.search(kind)


def parse_release(text, today):
    """(date or None, upcoming?) from Steam's release text: "Nov 15, 2026", "Q1 2027", "Coming soon"."""
    t = html.unescape(str(text or "")).strip()
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y"):
        try:
            d = datetime.strptime(t, fmt).date()
            return d, d > today
        except ValueError:
            pass
    for fmt in ("%b %Y", "%B %Y"):
        try:
            d = datetime.strptime(t, fmt).date()
            return d, d > today.replace(day=1) or d == today.replace(day=1)
        except ValueError:
            pass
    m = re.match(r"^Q([1-4])\s+(\d{4})$", t, re.I)
    if m:
        d = date(int(m.group(2)), 3 * int(m.group(1)) - 2, 1)
        return d, True
    m = re.match(r"^(\d{4})$", t)
    if m:
        return date(int(m.group(1)), 1, 1), int(m.group(1)) >= today.year
    return None, bool(t)   # "Coming soon", "To be announced"


def days_since(d, today):
    try:
        return (today - date.fromisoformat(d)).days
    except (TypeError, ValueError):
        return 10 ** 6


# ------------------------------------------------------------------ Steam

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def parse_rows(text):
    """Games from a Steam search results page: [{"appid", "name", "released", "reviews", "positive", "tags"}]."""
    out = []
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", text or "", re.S):
        attrs, body = m.groups()
        appid = re.search(r'data-ds-appid="(\d+)"', attrs)
        if not appid or "data-ds-bundleid" in attrs or "data-ds-packageid" in attrs:
            continue
        title = re.search(r'<span class="title">(.*?)</span>', body, re.S)
        if not title:
            continue
        tagids = re.search(r'data-ds-tagids="\[([^\]]*)\]"', attrs)
        released = re.search(r'class="search_released[^"]*"[^>]*>(.*?)</div>', body, re.S)
        reviews = re.search(r"of the ([\d,]+) user reviews", body)
        positive = re.search(r"(\d+)% of the [\d,]+ user reviews", body)
        out.append({"appid": int(appid.group(1)), "name": html.unescape(title.group(1)).strip(),
                    "released": html.unescape(released.group(1)).strip() if released else "",
                    "reviews": int(reviews.group(1).replace(",", "")) if reviews else 0,
                    "positive": int(positive.group(1)) if positive else None,
                    "tags": [int(t) for t in re.findall(r"\d+", tagids.group(1))] if tagids else []})
    return out


def steam_search(params):
    q = {"start": 0, "count": STEAM_COUNT, "category1": 998, "infinite": 1, "cc": "us", "l": "english", **params}
    time.sleep(STEAM_PAUSE)
    return parse_rows(fetch(SEARCH_URL.format(urllib.parse.urlencode(q))).get("results_html"))


def tag_names(state, today):
    """{tag id: name}, from Steam once a month."""
    cache = state.setdefault("tags", {})
    if cache.get("names") and days_since(cache.get("date"), today) < LOOKUP_EVERY:
        return {int(k): v for k, v in cache["names"].items()}
    got = fetch(TAGS_URL)
    cache.update({"date": iso(today), "names": {str(t["tagid"]): t["name"] for t in got if t.get("tagid")}})
    return {int(k): v for k, v in cache["names"].items()}


def steam_lists(tag_ids, today):
    """{appid: row with "lists": [[list, tag name, rank]]} from every list of every tag."""
    rows = {}
    for tag, tid in tag_ids.items():
        for key, (_, params, count) in LISTS.items():
            for rank, r in enumerate(steam_search({"tags": tid, "count": count, **params}), 1):
                row = rows.setdefault(r["appid"], {**r, "lists": []})
                row["lists"].append([key, tag, rank])
                row["reviews"] = max(row["reviews"], r["reviews"])
    print(f"  Steam: {len(rows)} games in {len(tag_ids)} tags' lists")
    return rows


def steam_lookup(name, appid=None):
    """The Steam game called `name` (or with `appid`): a search results row, or None."""
    rows = steam_search({"term": name, "count": 10})
    if appid:
        for r in rows:
            if r["appid"] == appid:
                return r
    want, want_short = norm(name), short(name)
    for r in rows:
        if norm(r["name"]) == want or short(r["name"]) == want_short:
            return r
    return None


def players_now(appid):
    time.sleep(STEAM_PAUSE)
    got = fetch(PLAYERS_URL.format(appid)).get("response") or {}
    return got.get("player_count") if got.get("result") == 1 else None


def reviews_now(appid):
    time.sleep(STEAM_PAUSE)
    got = (fetch(DETAILS_URL.format(appid)).get(str(appid)) or {})
    if not got.get("success"):
        return None
    return ((got.get("data") or {}).get("recommendations") or {}).get("total", 0)


def remember(history, today, value):
    """Append today's value to a [[date, n]] history, one per day, the last HISTORY_DAYS."""
    history = [h for h in history if h[0] != iso(today)] + [[iso(today), value]]
    return [h for h in history if days_since(h[0], today) <= HISTORY_DAYS]


def week_ago(history, today):
    """The value 6-9 days back nearest to 7, or None."""
    best = None
    for d, v in history:
        age = days_since(d, today)
        if 6 <= age <= 9 and (best is None or abs(age - 7) < abs(best[0] - 7)):
            best = (age, v)
    return best[1] if best else None


# ------------------------------------------------------------------ YouTube competition

def youtube_counts(creds, name, now):
    """Videos uploaded in the last COMPETITION_DAYS days on `name`, and their views. Counts only."""
    after = (now - timedelta(days=COMPETITION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.urlencode({"part": "id", "type": "video", "q": f'"{name}"', "publishedAfter": after,
                                "order": "viewCount", "maxResults": 50})

    def get(url):
        req = urllib.request.Request(url, headers=creds.headers())
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    found = get(f"{DATA_API}/search?{q}")
    ids = [i["id"]["videoId"] for i in found.get("items") or [] if (i.get("id") or {}).get("videoId")]
    views = []
    if ids:
        stats = get(f"{DATA_API}/videos?part=statistics&id={','.join(ids)}&maxResults=50")
        views = [int((i.get("statistics") or {}).get("viewCount") or 0) for i in stats.get("items") or []]
    return {"videos": len(ids), "more": bool(found.get("nextPageToken")), "views": sum(views),
            "top": max(views) if views else 0}


# ------------------------------------------------------------------ the radar

class Radar:
    """
    One run. `ctx` carries what discover.py already knows: your game names
    ({key: label}), your Steam appids, your games ranked by views with their
    views, what you dismissed, the baseline, the search budget, and `room()`
    (searches this run may still spend).
    """

    def __init__(self, ctx, settings, today, now, network, have_key):
        self.ctx, self.today, self.now = ctx, today, now
        self.network, self.have_key = network, have_key
        cfg = settings.setdefault("radar", {})
        cfg.setdefault("_how", "seeds: Google Trends genre searches; steam_tags: Steam tags whose lists are read. "
                               "Edit freely; a seed's results come with its next pull.")
        self.seeds = [s.strip().lower() for s in cfg.setdefault("seeds", list(SEEDS)) if str(s).strip()]
        self.steam_tags = [str(t).strip() for t in cfg.setdefault("steam_tags", list(STEAM_TAGS)) if str(t).strip()]
        self.state = load_json(STATE_PATH, {})
        self.health, self.spent = [], 0

    # -------------------------------------------------- spending

    def room(self):
        return min(self.ctx["max"] - self.spent, self.ctx["budget"].left())

    def search(self, what, call):
        """One Google Trends search, counted. Returns its result, or None after a failure."""
        self.spent += 1
        try:
            return call()
        except trends.TrendsError as e:
            print(f"  ! {what}: {e}")
            self.health.append({"level": "error", "message": f"Google Trends search for {what} failed: {e}"})
            if "401" in str(e) or "Invalid API key" in str(e):
                self.spent = 10 ** 6   # a bad key: stop searching this run
            return None

    # -------------------------------------------------- Steam (free)

    def read_steam(self):
        st = self.state.setdefault("steam", {})
        try:
            names = tag_names(self.state, self.today)
            by_name = {v.lower(): k for k, v in names.items()}
            ids = {t: by_name[t.lower()] for t in self.steam_tags if t.lower() in by_name}
            missing = [t for t in self.steam_tags if t.lower() not in by_name]
            if missing:
                self.health.append({"level": "warn", "message": "Steam has no tag called " + ", ".join(
                    f"“{t}”" for t in missing) + " (settings → radar → steam_tags in data/discover.json)."})
            rows = steam_lists(ids, self.today)
            if rows:
                st.update({"date": iso(self.today), "rows": {str(k): v for k, v in rows.items()}})
        except Exception as e:
            print(f"  ! Steam lists: {str(e)[:160]}")
            self.health.append({"level": "warn", "message": f"Steam's lists could not be read ({str(e)[:80]}); "
                                "the last ones are used."})

    def lookups(self, names_wanted):
        """Steam rows for games known by name only (Google topics, your games), kept LOOKUP_EVERY days."""
        cache = self.state.setdefault("lookup", {})
        done = 0
        for name, appid in names_wanted:
            key = norm(name)
            e = cache.get(key)
            if e and days_since(e.get("date"), self.today) < LOOKUP_EVERY:
                continue
            if done >= LOOKUPS_RUN:
                break
            done += 1
            try:
                r = steam_lookup(name, appid)
            except Exception as ex:
                print(f"  ! Steam lookup {name}: {str(ex)[:120]}")
                continue
            cache[key] = {**(r or {"none": True}), "date": iso(self.today)}

    def momentum(self, games):
        hist = self.state.setdefault("momentum", {})
        for c in games:
            if not c.get("appid"):
                continue
            h = hist.setdefault(str(c["appid"]), {"players": [], "reviews": []})
            try:
                p = players_now(c["appid"])
                if p is not None:
                    h["players"] = remember(h["players"], self.today, p)
                r = reviews_now(c["appid"])
                if r is not None:
                    h["reviews"] = remember(h["reviews"], self.today, r)
            except Exception as e:
                print(f"  ! Steam momentum {c['name']}: {str(e)[:120]}")
        for k in list(hist):   # keep only games still on the radar
            if not any(str(c.get("appid")) == k for c in games):
                if all(days_since(d, self.today) > HISTORY_DAYS for d, _ in hist[k]["players"] + hist[k]["reviews"]):
                    del hist[k]

    # -------------------------------------------------- Google Trends

    def seeds_due(self):
        pulls = self.state.setdefault("seeds", {})
        due = []
        for s in self.seeds:
            for kind in ("topics", "queries"):
                p = (pulls.get(s) or {}).get(kind)
                age = days_since(p["date"], self.today) if p else None
                if p is None or age >= SEED_EVERY:
                    due.append((0 if p is None else 1, -(age or 0), self.seeds.index(s), kind != "topics", s, kind))
        due.sort()
        return [(s, kind) for *_, s, kind in due]

    def pull_seeds(self):
        budget = self.ctx["budget"]
        for seed, kind in self.seeds_due():
            if self.room() <= 0:
                break
            fn = trends.related_topics if kind == "topics" else trends.related_queries
            got = self.search(f"“{seed}” ({kind})", lambda: fn(seed, SEED_RANGE, cat=trends.GAMES_CAT, budget=budget))
            if got is None:
                continue
            entry = {"date": iso(self.today), "range": SEED_RANGE, "cat": trends.GAMES_CAT, **got}
            self.state["seeds"].setdefault(seed, {})[kind] = entry
            archive(f"seed-{slug(seed)}-{kind}", {"seed": seed, "kind": kind, **entry}, self.today)
            if kind == "queries":
                self.saw_themes(seed, got)

    def resolve(self, games):
        """A Google topic (mid) for shortlisted games that have none: one autocomplete search each, kept."""
        topics = self.state.setdefault("topic", {})
        budget, done = self.ctx["budget"], 0
        for c in games:
            if c.get("mid") or done >= RESOLVE_RUN or self.room() <= 0:
                continue
            e = topics.get(c["key"])
            if e and (e.get("mid") or days_since(e.get("date"), self.today) < TOPIC_RETRY):
                continue
            name = display_short(c["name"])
            got = self.search(f"“{name}” (topic)", lambda: trends.autocomplete(name, budget=budget))
            done += 1
            if got is None:
                continue
            want = {norm(c["name"]), short(c["name"])}
            pick = next((t for t in got if is_game_topic(t) and norm(t["title"]) in want), None) or \
                next((t for t in got if is_game_topic(t) and short(t["title"]) in want), None)
            topics[c["key"]] = {**(pick or {"none": True}), "date": iso(self.today)}
            if pick:
                c["mid"] = pick["mid"]

    def measure(self, games, base):
        """The shortlist's sizes against the baseline, four to a search."""
        if not base:
            return
        sizes = self.state.setdefault("sizes", {})
        due = [c for c in games if c.get("mid") and (c["key"] not in sizes or sizes[c["key"]].get("mid") != c["mid"]
                                                     or days_since(sizes[c["key"]].get("date"), self.today) >= SIZE_EVERY)]
        budget, runs = self.ctx["budget"], 0
        while due and runs < SIZE_RUN and self.room() > 0:
            batch, seen = [], set()
            for c in list(due):
                if len(batch) == trends.MAX_TERMS - 1:
                    break
                due.remove(c)
                if c["mid"] not in seen:
                    seen.add(c["mid"])
                    batch.append(c)
            runs += 1
            terms = [base["term"]] + [c["mid"] for c in batch]
            got = self.search("game sizes", lambda: trends.interest_over_time(terms, SIZE_RANGE, budget=budget))
            if got is None:
                continue
            archive("radar-sizes", {"vs": base["term"], "range": SIZE_RANGE, "terms": terms,
                                    "games": [c["name"] for c in batch], **got}, self.today)
            series = list(got["series"].values())
            ref = mean(series[0]) if series else 0.0
            if ref <= 0:
                print(f"  ! “{base['term']}” has no data in this comparison")
                continue
            for i, c in enumerate(batch):
                sizes[c["key"]] = {**measure_series(series[i + 1] if i + 1 < len(series) else [], ref, got["dates"],
                                                    base["monthly"]), "mid": c["mid"], "date": iso(self.today)}

    def measure_genres(self, base):
        """The seeds against the baseline once a month: which genre grows overall."""
        g = self.state.setdefault("genres", {})
        if not base or (g.get("date") and days_since(g["date"], self.today) < GENRES_EVERY
                        and set(g.get("seeds", {})) >= set(self.seeds)):
            return
        budget, out = self.ctx["budget"], {}
        for i in range(0, len(self.seeds), trends.MAX_TERMS - 1):
            if self.room() <= 0:
                return   # finish next run: nothing is saved half done
            batch = self.seeds[i:i + trends.MAX_TERMS - 1]
            terms = [base["term"]] + batch
            got = self.search("genre sizes", lambda: trends.interest_over_time(terms, SIZE_RANGE, budget=budget))
            if got is None:
                return
            series = list(got["series"].values())
            ref = mean(series[0]) if series else 0.0
            for j, s in enumerate(batch):
                if ref > 0:
                    out[s] = measure_series(series[j + 1] if j + 1 < len(series) else [], ref, got["dates"],
                                            base["monthly"])
        archive("radar-genres", {"vs": base["term"], "seeds": out}, self.today)
        g.update({"date": iso(self.today), "vs": base["term"], "seeds": out})

    # -------------------------------------------------- themes (areas heating up)

    def theme_rows(self, known_games):
        """Every seed query that names no game: (seed, kind, entry, theme words)."""
        rows = []
        genre_words = set().union(*(words(s) for s in self.seeds)) if self.seeds else set()
        for seed in self.seeds:
            p = ((self.state.get("seeds") or {}).get(seed) or {}).get("queries") or {}
            seed_words = genre_words   # a theme is beyond every genre: "cozy", not "builder"
            for kind in ("rising", "top"):
                for q in p.get(kind) or []:
                    low = re.sub(r"\bco[\s-]?op\b", "coop", q["query"].lower())
                    if JUNK.search(low) or foreign(low) or any(mentions(low, g) for g in known_games):
                        continue
                    ws = [w for w in words(low) if w not in seed_words and w not in GENERIC and w not in PLATFORM
                          and not w.isdigit()]
                    if ws:
                        rows.append((seed, kind, q, ws))
        return rows

    def saw_themes(self, seed, got):
        """Remember the day each theme was rising in a fresh pull: SUGGEST_ROUNDS of them make a seed."""
        seen = self.state.setdefault("themes_seen", {})
        seed_words = set().union(*(words(s) for s in self.seeds))
        for q in got.get("rising") or []:
            low = re.sub(r"\bco[\s-]?op\b", "coop", q["query"].lower())
            if JUNK.search(low):
                continue
            for w in {w for w in words(low) if w not in seed_words and w not in GENERIC and w not in PLATFORM}:
                days = seen.setdefault(w, [])
                if iso(self.today) not in days:
                    days.append(iso(self.today))
                seen[w] = sorted(days)[-12:]

    # -------------------------------------------------- putting it together

    def candidates(self, names, labels, your_appids, dismissed, titles=()):
        """
        {key: game} from Steam's lists and the seeds' topics, without yours: a
        game in your titles, one of your Steam apps, one any title of yours
        names (even once), or one you dismissed. A sequel to one of yours stays,
        marked as following it.
        """
        tagname = {int(k): v for k, v in ((self.state.get("tags") or {}).get("names") or {}).items()}
        lookup = self.state.get("lookup") or {}
        pool = {}

        def add(key, name):
            return pool.setdefault(key, {"key": key, "name": name, "appid": None, "mid": None, "tags": [],
                                         "released": "", "reviews": 0, "positive": None, "why": [],
                                         "searches": []})

        def fill(c, row):
            c.update({"appid": row["appid"], "name": row["name"], "released": row.get("released", ""),
                      "positive": row.get("positive"), "tags": row.get("tags") or c["tags"]})
            c["reviews"] = max(c["reviews"], row.get("reviews") or 0)

        for appid, row in ((self.state.get("steam") or {}).get("rows") or {}).items():
            c = add(f"app:{appid}", row["name"])
            fill(c, row)
            for lst, tag, rank in row.get("lists") or []:
                c["why"].append({"kind": "steam", "list": lst, "tag": tag, "rank": rank})
        for seed in self.seeds:
            p = ((self.state.get("seeds") or {}).get(seed) or {}).get("topics") or {}
            for kind in ("rising", "top"):
                for t in p.get(kind) or []:
                    if not is_game_topic(t):
                        continue
                    row = lookup.get(norm(t["title"]))
                    key = f"app:{row['appid']}" if row and row.get("appid") else f"topic:{t['mid'] or norm(t['title'])}"
                    c = add(key, t["title"])
                    if row and row.get("appid"):
                        if not c["appid"]:
                            fill(c, row)
                    c["mid"] = c["mid"] or t.get("mid") or None
                    c["why"].append({"kind": "google", "seed": seed, "list": kind, "rise": t.get("rise"),
                                     "breakout": bool(t.get("breakout")), "score": t.get("score")})
        topics = self.state.get("topic") or {}
        for c in pool.values():
            if not c["mid"] and (topics.get(c["key"]) or {}).get("mid"):
                c["mid"] = topics[c["key"]]["mid"]

        hidden = {norm(d["item"]) for d in dismissed if d.get("game") in (None, "", "new games")}
        bases = {}
        for k in names:
            bases.setdefault(base_of(k), []).append(k)
        out = {}
        for key, c in pool.items():
            full, sh = norm(c["name"]), short(c["name"])
            if c["appid"] in your_appids or full in names or sh in names or full in hidden or sh in hidden:
                continue
            named = re.compile(r"(?<![\w])" + re.escape(sh) + r"(?![\w])")
            if len(sh) >= 4 and any(named.search(t) for t in titles):
                continue   # a video of yours names it
            mine = game_of(full, names)
            follows = None
            if mine:
                rest = full[len(mine):].split() if full.startswith(mine) else []
                if not (rest and SEQUEL.match(rest[0])):
                    continue   # an edition of yours
                follows = mine
            elif len(base_of(sh)) >= 4 and base_of(sh) in bases and base_of(sh) != sh:
                follows = bases[base_of(sh)][0]   # "tropico 8" after your "tropico 6"
            c["follows"] = labels.get(follows) if follows else None
            c["tag_names"] = [tagname[t] for t in c["tags"] if t in tagname]
            out[key] = c
        return out

    def attach_searches(self, games):
        """The seeds' queries that name a game, under that game."""
        by_name = sorted(((short(c["name"]), c) for c in games.values() if len(short(c["name"])) >= 4),
                         key=lambda x: -len(x[0]))
        for seed in self.seeds:
            p = ((self.state.get("seeds") or {}).get(seed) or {}).get("queries") or {}
            for kind in ("rising", "top"):
                for q in p.get(kind) or []:
                    low = q["query"].lower()
                    if JUNK.search(low):
                        continue
                    for name, c in by_name:
                        if mentions(low, name):
                            if not any(s["query"].lower() == low for s in c["searches"]):
                                c["searches"].append({"query": q["query"], "seed": seed, "list": kind,
                                                      "rise": q.get("rise"), "breakout": bool(q.get("breakout")),
                                                      "score": q.get("score")})
                            break

    def profile(self, ranked, views, your_tags):
        """{tag id: weight}: the Steam tags of your games, weighted by their views (sums to 1)."""
        total, prof = 0.0, Counter()
        for g in ranked:
            tags = your_tags.get(g) or []
            v = views.get(g, 0)
            if tags and v > 0:
                total += v
                for t in tags:
                    prof[t] += v
        return {t: w / total for t, w in prof.items()} if total else {}

    def fit(self, c, prof, your_tags, ranked, labels):
        if not prof or not c["tags"]:
            return None, [], []
        best = sum(sorted(prof.values(), reverse=True)[:len(c["tags"])])
        got = sum(prof.get(t, 0) for t in c["tags"])
        tagname = {int(k): v for k, v in ((self.state.get("tags") or {}).get("names") or {}).items()}
        shared = sorted((t for t in c["tags"] if t in prof), key=lambda t: -prof[t])
        like = [labels[g] for g in ranked if len(set(your_tags.get(g) or []) & set(c["tags"])) >= 3][:2]
        return (round(got / best, 2) if best else None), [tagname.get(t, str(t)) for t in shared[:3]], like


def measure_series(vals, ref_avg, dates, base_monthly):
    """
    A game's (or genre's) size from its line beside the baseline: searches a
    month at its level (an upper bound when too small to chart), its trend
    (last four weeks against the first four of the 90 days), and its line by
    week in searches a month.
    """
    sz = size_of(vals, ref_avg, dates)
    upper = sz["level"] < MIN_POINTS
    monthly = base_monthly * (sz["floor"] if upper else sz["ratio"]) if sz["ratio"] is not None else None
    first, last = mean(vals[:28]), mean(vals[-28:])
    per = base_monthly / ref_avg if ref_avg > 0 else None
    return {"monthly": round(monthly) if monthly is not None else None, "upper": upper,
            "trend": round(last / first - 1, 3) if first > 0 else None, "fresh": first == 0 and last > 0,
            "spike": sz["spike"],
            "weekly": [round(mean(vals[i:i + 7]) * per) for i in range(0, len(vals), 7)] if per and vals else []}


def momentum_factor(size):
    """x0.5 to x3 from the Google trend: flat is x1, doubled x2; a game that was not searched before is x3."""
    if not size:
        return 1.0
    if size.get("fresh"):
        return 3.0
    t = size.get("trend")
    return max(0.5, min(3.0, 1 + t)) if t is not None else 1.0


def guess(c):
    """A first guess before any Google size: reviews (how many play it) and why it surfaced."""
    s = math.log10(10 + (c.get("reviews") or 0))
    bonus = 0.0
    for w in c["why"]:
        if w["kind"] == "google":
            bonus += (3 if w["breakout"] else 2) if w["list"] == "rising" else 1
        else:
            bonus += {"top": 1.0, "trending": 0.5, "upcoming": 0.5}.get(w["list"], 0)
    return round((s + min(bonus, 5)) * (0.5 + (c.get("fit") or 0)), 3)


def why_summary(why):
    """The strongest reasons, one per source: [{"kind", ...}] without repeats."""
    google = [w for w in why if w["kind"] == "google"]
    steam = [w for w in why if w["kind"] == "steam"]
    out = []
    rising = sorted((w for w in google if w["list"] == "rising"), key=lambda w: (not w["breakout"], -(w["rise"] or 0)))
    out += rising[:2]
    if not rising:
        out += sorted((w for w in google if w["list"] == "top"), key=lambda w: -(w["score"] or 0))[:1]
    order = {"top": 0, "trending": 1, "upcoming": 2}
    seen = set()
    for w in sorted(steam, key=lambda w: (order.get(w["list"], 9), w["rank"])):
        if w["list"] not in seen:
            seen.add(w["list"])
            out.append(w)
    return out[:4]


def is_new(c, today):
    """Out in the last NEW_FOR_DAYS days or not out yet; without a Steam date, new when it rises on Google."""
    d, upcoming = parse_release(c["released"], today)
    if d or upcoming:
        return upcoming or (today - d).days <= NEW_FOR_DAYS
    return any(w["kind"] == "google" and w["list"] == "rising" for w in c["why"])


def split(games, counts):
    """The first counts[0] new games and the first counts[1] established ones, in their order."""
    new = [c for c in games if c["new_game"]][:counts[0]]
    old = [c for c in games if not c["new_game"]][:counts[1]]
    keep = {id(c) for c in new + old}
    return [c for c in games if id(c) in keep]


def run(ctx, settings, today, now, network, have_key):
    """
    The radar and the areas heating up: (radar, areas, health, searches spent).
    `network` False (an offline or intake run) rebuilds from saved state only.
    """
    r = Radar(ctx, settings, today, now, network, have_key)
    names, labels = ctx["names"], ctx["labels"]
    ranked, views, base = ctx["ranked"], ctx["views"], ctx["base"]

    # Your games' Steam tags, for fit: looked up by name, the Steam app from data/steam.json first.
    yours = r.state.setdefault("yours", {})
    if network:
        r.read_steam()
        r.lookups([(labels[g], ctx["your_appid"].get(g)) for g in ranked])
    lookup = r.state.get("lookup") or {}
    for g in ranked:
        row = lookup.get(norm(labels[g]))
        if row and row.get("appid"):
            yours[g] = {"appid": row["appid"], "tags": row.get("tags") or []}
    your_tags = {g: (yours.get(g) or {}).get("tags") or [] for g in ranked}
    prof = r.profile(ranked, views, your_tags)

    if network and have_key and r.room() > 0:
        r.pull_seeds()
    if network:
        # Steam rows for the games Google named, so they get tags and reviews.
        titles = []
        for s in r.seeds:
            p = ((r.state.get("seeds") or {}).get(s) or {}).get("topics") or {}
            titles += [(t["title"], None) for k in ("rising", "top") for t in p.get(k) or [] if is_game_topic(t)]
        r.lookups(titles)

    games = r.candidates(names, labels, ctx["your_appids"], ctx["dismissed"], ctx.get("titles") or ())
    known = {short(c["name"]) for c in games.values() if len(short(c["name"])) >= 4} | set(names)
    for s in r.seeds:
        p = ((r.state.get("seeds") or {}).get(s) or {}).get("topics") or {}
        known |= {short(t["title"]) for k in ("rising", "top") for t in p.get(k) or []
                  if is_game_topic(t) and len(short(t["title"])) >= 4}
    r.attach_searches(games)
    for c in games.values():
        c["fit"], c["shared"], c["like"] = r.fit(c, prof, your_tags, ranked, labels)
        c["guess"] = guess(c)
        c["new_game"] = is_new(c, today)
    order = sorted(games.values(), key=lambda c: -c["guess"])
    shortlist = split(order, SHORTLIST)

    if network and have_key and r.room() > 0:
        r.resolve(shortlist)
        r.measure(shortlist, base)
        r.measure_genres(base)

    sizes = r.state.get("sizes") or {}
    for c in games.values():
        sz = sizes.get(c["key"])
        c["size"] = sz if sz and c.get("mid") and sz.get("mid") == c["mid"] else None
        if c["size"] and c["size"].get("monthly"):
            c["score"] = round(math.log10(1 + c["size"]["monthly"]) * momentum_factor(c["size"])
                               * (0.5 + (c["fit"] or 0)), 3)
    order = sorted(games.values(), key=lambda c: (c.get("score") is None, -(c.get("score") or c["guess"])))
    top = split(order, KEEP)

    if network:
        r.momentum(split(top, MOMENTUM_GAMES))
        creds = ctx.get("youtube")
        if creds:
            comp = r.state.setdefault("competition", {})
            for c in split(top, COMPETITION_GAMES):
                e = comp.get(c["key"])
                if e and days_since(e.get("date"), today) < COMPETITION_EVERY:
                    continue
                try:
                    comp[c["key"]] = {**youtube_counts(creds, display_short(c["name"]), now), "date": iso(today)}
                except Exception as ex:
                    print(f"  ! YouTube count {c['name']}: {str(ex)[:120]}")
                    break
            for k in [k for k in comp if days_since(comp[k].get("date"), today) > COMPETITION_DAYS]:
                del comp[k]   # API policy: nothing about other channels kept past 30 days

    # First seen, for "New".
    first = r.state.setdefault("first_seen", {})
    started = r.state.setdefault("since", iso(today))
    hist = r.state.get("momentum") or {}
    comp = r.state.get("competition") or {}
    out = []
    for c in top:
        f = first.setdefault(c["key"], iso(today))
        h = hist.get(str(c.get("appid"))) or {}
        p_now = h["players"][-1][1] if h.get("players") else None
        p_week = week_ago(h.get("players") or [], today)
        rv_now = h["reviews"][-1][1] if h.get("reviews") else None
        rv_week = week_ago(h.get("reviews") or [], today)
        k = comp.get(c["key"])
        monthly = (c["size"] or {}).get("monthly")
        d, upcoming = parse_release(c["released"], today)
        out.append({
            "key": c["key"], "name": c["name"], "appid": c["appid"],
            "group": "new" if c["new_game"] else "established",
            "steam_url": f"https://store.steampowered.com/app/{c['appid']}/" if c["appid"] else None,
            "search_name": display_short(c["name"]), "released": c["released"],
            "release_date": iso(d) if d else None, "upcoming": upcoming,
            "reviews": c["reviews"] or None, "positive": c["positive"], "tags": c["tag_names"][:5],
            "fit": c["fit"], "shared": c["shared"], "like": c["like"], "follows": c["follows"],
            "why": why_summary(c["why"]), "searches": sorted(c["searches"], key=lambda s: (
                s["list"] != "rising", not s["breakout"], -(s["rise"] or 0), -(s["score"] or 0)))[:SEARCHES_PER_GAME],
            "topic": bool(c.get("mid")), "mid": c.get("mid"),
            "size": {k2: c["size"][k2] for k2 in ("monthly", "upper", "trend", "fresh", "spike", "weekly", "date")}
            if c["size"] else None,
            "momentum": {"players": p_now, "players_week": p_week, "reviews": rv_now,
                         "reviews_week": (rv_now - rv_week) if rv_now is not None and rv_week is not None else None},
            "competition": {**{k2: k[k2] for k2 in ("videos", "more", "views", "top", "date")},
                            "few": bool(monthly and not k["more"] and k["videos"] < FEW_VIDEOS
                                        and monthly >= FEW_MIN_MONTHLY)} if k else None,
            "score": c.get("score"), "guess": c["guess"], "measured": c["size"] is not None,
            "first_seen": f, "new": f != started and days_since(f, today) < NEW_DAYS,
        })
    for k2 in [k2 for k2 in first if days_since(first[k2], today) > 180 and k2 not in games]:
        del first[k2]

    # Areas heating up.
    areas = themes(r, known, games, your_tags, labels, ranked, ctx["dismissed"])
    pulls = r.state.get("seeds") or {}
    radar = {
        "games": out, "seeds": r.seeds, "steam_tags": r.steam_tags,
        "pulled": {s: {k2: (pulls.get(s) or {}).get(k2, {}).get("date") for k2 in ("topics", "queries")}
                   for s in r.seeds},
        "steam_date": (r.state.get("steam") or {}).get("date"),
        "profile": sorted(({"tag": ((r.state.get("tags") or {}).get("names") or {}).get(str(t), str(t)),
                            "share": round(w, 3)} for t, w in prof.items()), key=lambda x: -x["share"])[:8],
        "candidates": len(games), "measured": sum(1 for c in games.values() if c.get("size")),
        "shortlist": sum(SHORTLIST), "new_for_days": NEW_FOR_DAYS, "few_videos": FEW_VIDEOS, "few_min_monthly": FEW_MIN_MONTHLY,
        "competition_days": COMPETITION_DAYS, "youtube": bool(ctx.get("youtube")),
    }
    if network:
        write_json(os.path.basename(STATE_PATH), r.state)
    return radar, areas, r.health, min(r.spent, ctx["max"])


def themes(r, known, games, your_tags, labels, ranked, dismissed):
    """Areas heating up: themes with a rising search, their example games, and the seeds' own sizes."""
    hidden = {norm(d["item"]) for d in dismissed if d.get("game") in (None, "", "areas")}
    rows = r.theme_rows(known)
    freq = Counter(w for _, _, _, ws in rows for w in set(ws))
    groups = {}
    for seed, kind, q, ws in rows:
        head = max(ws, key=lambda w: (freq[w], ws.index(w)))   # the most shared word; ties: the later one
        g = groups.setdefault(head, {"theme": head, "queries": [], "seeds": set()})
        g["seeds"].add(seed)
        if any(x["query"].lower() == q["query"].lower() for x in g["queries"]):
            continue
        g["queries"].append({"query": q["query"], "seed": seed, "list": kind, "rise": q.get("rise"),
                             "breakout": bool(q.get("breakout")), "score": q.get("score")})
    tagname = {int(k): v for k, v in ((r.state.get("tags") or {}).get("names") or {}).items()}
    tag_of = {}
    for tid, name in tagname.items():
        tag_of.setdefault(re.sub(r"[^a-z0-9]", "", name.lower()), tid)
    seen = r.state.get("themes_seen") or {}
    out = []
    for head, g in groups.items():
        g["queries"].sort(key=lambda x: (x["list"] != "rising", not x["breakout"], -(x["rise"] or 0),
                                         -(x["score"] or 0)))
        rising = [x for x in g["queries"] if x["list"] == "rising"]
        if not rising or head in hidden or norm(rising[0]["query"]) in hidden:
            continue
        tid = tag_of.get(head) or tag_of.get(head + "s")
        examples = [c["name"] for c in sorted(games.values(), key=lambda c: -(c.get("score") or c["guess"]))
                    if tid and tid in c["tags"]][:3]
        covered = [labels[gm] for gm in ranked if tid and tid in (your_tags.get(gm) or [])][:2]
        days = sorted(seen.get(head) or [])
        rounds, last = 0, None
        for d in days:
            if last is None or days_since(last, date.fromisoformat(d)) >= SEED_EVERY - 4:
                rounds, last = rounds + 1, d
        label = rising[0]["query"]
        out.append({"theme": head, "label": label, "queries": g["queries"][:8], "seeds": sorted(g["seeds"]),
                    "rising": len(rising), "breakout": any(x["breakout"] for x in rising),
                    "rise": max((x["rise"] or 0) for x in rising), "tag": tagname.get(tid) if tid else None,
                    "examples": examples, "covered": covered, "rounds": rounds,
                    "suggest": rounds >= SUGGEST_ROUNDS and label.lower() not in r.seeds})
    out.sort(key=lambda t: (not t["breakout"], -t["rising"], -len(t["seeds"]), -t["rise"]))
    g = r.state.get("genres") or {}
    genres = [{"seed": s, **(g.get("seeds") or {}).get(s, {})} for s in r.seeds]
    genres.sort(key=lambda x: -(x.get("monthly") or 0))
    return {"themes": out[:12], "genres": genres, "genres_date": g.get("date"), "suggest_rounds": SUGGEST_ROUNDS}
