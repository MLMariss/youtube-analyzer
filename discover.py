#!/usr/bin/env python3
"""
Discover: what is not on the dashboard yet. The roadmap is in
docs/search-demand-plan.md; this is Phase 1.

Unanswered questions in your games
----------------------------------
For the games you cover that still bring views, Google's related searches
(web search, worldwide, the last three months) are pulled from Google Trends,
and every query one of your videos already answers is dropped. What is left
is what people ask about a game you are known for that you have not made a
video on: "tropico 6 crash on startup", "how to stop rebels".

Which games, and how often
    Games are found in your titles (monitor.game_names) and ranked by views
    over the last 28 days. The top 12 are searched every 14 days, the next 12
    every 30, at most RUN_MAX searches a run so the daily job spreads them
    out. Every search comes out of the cycle budget in trends.py.

Where
    All of web search, not only Google's Games category: a game that reaches
    the news, social media or business pages is a trend too. Only names that
    are everyday words (AMBIGUOUS: "Foundation", "Grounded") are searched in
    the Games category, which keeps them the game and not the make-up.

What is dropped
    - piracy, shop and spec searches (crack, price, system requirements...),
      in other languages too (скачать, descargar, kaufen...)
    - a query that is only the game name and a platform ("tropico 6 ps4")
    - a query whose words all appear in one of your titles on that game
    - a query whose words all appear in a YouTube search term that already
      brought those videos views: people already find you with it
    - anything you dismissed (a "Dismiss: ..." issue, from the dashboard)

How big it is
    A rise says nothing about size: +250% can be three people. So right after
    a game's related searches are pulled, one more search puts the game and up
    to four of its rising questions on one scale (interest over time, same 90
    days). Each question gets its share of the game's searches, at the busier
    of its three-month average and its last week (a problem that started
    five days ago counts at today's pace), and a check that it is not a
    one-day spike that already faded.

    Google never gives counts, so counts come from a baseline: Keyword
    Planner's monthly searches for one or more of your games, entered by hand
    under "settings" -> "searches_per_month" (a number, or a range such as
    "10K-100K"). One game in the middle is the anchor; every CALIBRATE_EVERY
    days the other games are compared with it, four to a search. A question's
    count is then its game's count times its share. Keyword Planner gives
    ranges without ad spend, so counts are order of magnitude.

What is shown
    A question needs MIN_MONTHLY searches a month when there are counts, or
    MIN_SHARE of its game's searches when there are not, and must be big
    enough to chart and not a faded one-day spike. The rest is listed under
    the game as small or one-off, so nothing vanishes. Searches in another
    language are a second class with a higher bar: among the game's top
    searches at FOREIGN_TOP or more, and FOREIGN_FACTOR times the count;
    the rest are listed under the game as other languages.

    Each question is sorted by intent (problem, how-to, news, topic), carries
    the video of yours that comes closest, and the Steam announcement it is
    about, if any. Queries that name another game ("tropico 5", "frostpunk")
    are kept apart as games searched alongside.

data/discover.json holds the result and three things to edit by hand: under
"settings" -> "games", a game's search "term", its "cat" (8 is Google's Games
category) or "skip": true, with "manual": true so the run leaves the entry
alone; and "settings" -> "searches_per_month". Raw pulls are archived in
data/discover_archive/<date>/, since related searches cannot be pulled again later.

Without SERPAPI_KEY, or with the budget spent, the saved pulls are filtered
again (against your newest titles) and nothing fails.

Usage:
    python discover.py                    # normal run (searches what is due)
    python discover.py --dry-run          # show what would be searched, change nothing
    python discover.py --max-searches 2   # spend at most 2 searches this run
    python discover.py --offline          # no searches; rebuild from saved pulls
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import actions
import trends
from monitor import game_names, game_of
from patches import stem, topic_words
from summarize import DATA_DIR, data_through, write_json

DISCOVER_PATH = os.path.join(DATA_DIR, "discover.json")
ARCHIVE_DIR = os.path.join(DATA_DIR, "discover_archive")

TOP_GAMES = 12          # searched every TOP_EVERY days
NEXT_GAMES = 12         # the next ones, every NEXT_EVERY days
TOP_EVERY = 14
NEXT_EVERY = 30
MIN_VIEWS = 20          # views over 28 days before a game is searched (monitor's COVERED_MIN)
RUN_MAX = 6             # searches per daily run: a game takes its pull and one or two sizing searches
PER_GAME = 8            # questions shown per game
SIDE_MAX = 8            # small or other-language searches listed per game
ALSO_MAX = 6            # other games searched alongside, per game
OWN_TERM_MIN = 2        # views a YouTube search term needs before it counts as yours
DATE_RANGE = "today 3-m"
NEW_DAYS = 7            # a question is marked new for this long after it first shows

# One-word game names that are everyday words: searched in Google's Games
# category, or "foundation" brings make-up. Add more by hand (a game's "cat"
# under settings -> games, with "manual": true).
AMBIGUOUS = {"foundation", "grounded", "icarus", "odyssey", "humankind", "windrose"}

# Sizing: the game and up to SIZE_SLOTS questions on one scale, per search.
SIZE_SLOTS = 4
SIZE_SEARCHES = 2       # sizing searches per pull at most
MIN_POINTS = 0.5        # a question under this level on the shared scale is too small to chart
RECENT_DAYS = 7         # a question's level is the busier of its three months and its last week
SPIKE_DAYS = 3          # a one-off: its busiest three days hold...
SPIKE_SHARE = 0.5       # ...half of its three months,
SPIKE_FADED = 0.25      # ...and its last three days are under a quarter of its peak
CALIBRATE_EVERY = 30    # days before the games are compared with the anchor again
CALIBRATE_RUN = 2       # calibration searches per run, first: counts for every game within days

# The bar a question must clear. Provisional: tune once a cycle of sizes is in.
MIN_MONTHLY = 100       # with counts: estimated searches a month, worldwide
MIN_SHARE = 0.01        # without counts: 1% of the game's own searches
FOREIGN_TOP = 20        # another language: among the game's top searches at this score (0-100) or more
FOREIGN_FACTOR = 4      # ...and four times the count or share an English question needs

# Never suggested: piracy, and shop, spec and listing searches.
JUNK = re.compile(
    r"\b(?:crack(?:ed)?|torrent|fitgirl|repack|igg|skidrow|codex|dodi|elamigos|steamunlocked|nosteam|"
    r"empress|apk|free download|download free|cd ?key|keys?|g2a|kinguin|eneba|instant gaming|"
    r"price|cost|sale|discount|cheap|buy|refund|metacritic|reviews?|rating|wiki|fandom|reddit|"
    r"system requirements?|requirements|specs|minimum|install size|file size|gb|trailer|release date|"
    r"download|size|"
    # the same in other languages: download, buy, free, torrent
    r"скачать|купить|торрент|бесплатно|descargar|comprar|gratis|kaufen|herunterladen|t[ée]l[ée]charger|"
    r"acheter|gratuit|baixar|pobierz|indir|scaricare)\b", re.I)
# Words that alone say nothing beyond the game: platforms, stores, years.
PLATFORM = {"pc", "ps4", "ps5", "playstation", "xbox", "one", "series", "x", "s", "switch", "nintendo", "mac",
            "macos", "mobile", "android", "ios", "iphone", "steam", "deck", "epic", "gog", "gamepass", "pass",
            "game", "games", "gameplay", "online", "offline", "edition", "remastered", "version", "demo", "vr"}
STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "be", "do", "does",
        "did", "can", "i", "my", "me", "you", "your", "it", "its", "this", "that", "how", "what", "why", "when",
        "where", "which", "who", "there", "at", "by", "from", "as", "if", "vs", "versus"}
YEAR = re.compile(r"^(?:19|20)\d\d$")
# Words that mark another language when written in plain English letters.
# Anything with letters English does not use (á, ő, ç, Cyrillic...) is
# another language already. Add words here as they turn up.
FOREIGN_WORDS = {
    "mody", "juego", "jugar", "trucos", "guia", "mapa", "spiel", "spielen", "tipps", "anleitung",
    "jeu", "astuces", "soluce", "jogo", "dicas", "gra", "poradnik", "porady", "spolszczenie", "oyun",
    "hile", "nasil", "nasıl", "yama", "traduzione", "traduccion", "traducao", "deutsch", "espanol", "francais",
    "polski", "magyar", "magyaritas", "cesky", "cestina", "ceske", "russkiy", "rusifikator", "como", "wie",
}

INTENTS = [
    ("problem", re.compile(r"\b(?:crash\w*|fix\w*|errors?|not (?:working|launching|loading|starting|opening|saving)|"
                           r"won'?t|can'?t|cannot|stuck|bugs?|bugged|buggy|broken|black screen|freez\w*|lag(?:s|gy|ging)?|stutter\w*|"
                           r"fps|corrupt\w*|missing|issues?|problems?)\b", re.I)),
    ("news", re.compile(r"\b(?:update|patch\w*|dlc|expansion|1\.0|roadmap|season|early access|announce\w*|"
                        r"coming|sequel)\b", re.I)),
    ("howto", re.compile(r"\b(?:how|best|guide|tips?|tutorial|build\w*|layouts?|strateg\w*|beginners?|cheats?|"
                         r"console|commands?|mods?|walkthrough|where|unlock\w*|get|farm\w*|money|start\w*|setup|"
                         r"settings?|seeds?|maps?|tier list|endings?|boss\w*|recipes?|controls?)\b", re.I)),
]
VOLUME_TITLE = "searches a month:"   # issues the dashboard's Set button opens
CLEAR_WORDS = {"clear", "remove", "delete", "none", "-"}
NOT_A_GAME = re.compile(r"\b(?:sale|gameplay|vs)\b", re.I)   # "steam summer sale", "player vs player"


def iso(d):
    return d.strftime("%Y-%m-%d")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "x"


def tokens(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", (text or "").lower())


def words(text, skip=()):
    """The words that carry a query's or title's meaning: stemmed, without stop words or `skip`."""
    out = set()
    for w in tokens(text):
        w = w.replace("'", "")
        if w in STOP or YEAR.match(w):
            continue
        w = stem(w)
        if w not in skip:
            out.add(w)
    return out


def intent_of(query):
    for name, pattern in INTENTS:
        if pattern.search(query):
            return name
    return "topic"


def is_foreign(query, key):
    """A search in another language: letters English does not use, or a word in FOREIGN_WORDS, beside the game's name."""
    name = set(re.findall(r"\w+", key.lower()))
    rest = [w for w in re.findall(r"\w+", query.lower()) if w not in name]
    return any(not w.isascii() for w in rest) or any(w in FOREIGN_WORDS for w in rest)


# ------------------------------------------------------------------ inputs

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ! could not read {os.path.basename(path)}: {str(e)[:120]}")
        return default


def views_by_game(games, window="28d"):
    """Views per game over `window`, from data/summary.json."""
    summary = load_json(os.path.join(DATA_DIR, "summary.json"), {})
    per_video = (summary.get("windows") or {}).get(window) or {}
    out = {}
    for vid, g in games.items():
        if g and vid in per_video:
            out[g] = out.get(g, 0) + (per_video[vid].get("views") or 0)
    return out


def own_search_terms(games):
    """{game: [search term words]}: YouTube searches that already bring the game's videos views."""
    detail = load_json(os.path.join(DATA_DIR, "traffic_detail.json"), {})
    videos = ((detail.get("all") or {}).get("videos")) or {}
    out = {}
    for vid, g in games.items():
        if not g:
            continue
        for term, n in ((videos.get(vid) or {}).get("5") or {}).items():
            if isinstance(n, (int, float)) and n >= OWN_TERM_MIN:
                out.setdefault(g, []).append(str(term))
    return out


def steam_news(keys):
    """{game: [Steam announcements]} from data/steam.json (patches.py keeps it fresh)."""
    steam = load_json(os.path.join(DATA_DIR, "steam.json"), {})
    apps, news = steam.get("apps") or {}, steam.get("news") or {}
    out = {}
    for key in keys:
        appid = (apps.get(key) or {}).get("appid")
        if appid:
            out[key] = (news.get(str(appid)) or {}).get("items") or []
    return out


def open_issues():
    """The repository's open issues (not pull requests), or [] without GITHUB_TOKEN."""
    try:
        batch = actions.github("GET", "/issues?state=open&per_page=100")
    except Exception as e:
        print(f"  ! could not read issues: {str(e)[:120]}")
        return []
    return [i for i in batch or [] if "pull_request" not in i]


def is_volume_issue(issue):
    labels = {label.get("name") for label in issue.get("labels", [])}
    return (issue.get("title") or "").lower().startswith(VOLUME_TITLE) or "discover-volume" in labels


def close_issue(issue, note, reason="completed"):
    try:
        actions.github("POST", f"/issues/{issue['number']}/comments", {"body": note})
        actions.github("PATCH", f"/issues/{issue['number']}", {"state": "closed", "state_reason": reason})
    except Exception as e:
        print(f"  ! could not close issue #{issue.get('number')}: {str(e)[:120]}")


def dismissed_from_issues(state, issues):
    """
    Add "Dismiss: ..." issues (the dashboard opens them) to the dismissed
    list, then close them with a note: the list in discover.json is the record.
    """
    have = {(d.get("game"), d.get("item")) for d in state["dismissed"]}
    for issue in issues:
        title = issue.get("title") or ""
        labels = {label.get("name") for label in issue.get("labels", [])}
        if is_volume_issue(issue) or (not title.lower().startswith("dismiss:") and "discover" not in labels):
            continue
        fields = actions.form_fields(issue.get("body"))
        item = (fields.get("what to hide") or title.split(":", 1)[-1].split("—")[0]).strip().strip('"“”').lower()
        game = (fields.get("game") or "").strip().lower() or None
        if not item:
            continue
        if (game, item) not in have:
            state["dismissed"].append({"item": item, "game": game, "date": issue.get("created_at", "")[:10],
                                       "issue": issue.get("number")})
            have.add((game, item))
            print(f"  hid “{item}” ({game or 'any game'}), issue #{issue.get('number')}")
        close_issue(issue, "Hidden from Discover. To show it again, remove it from `dismissed` in `data/discover.json`.")


def volumes_from_issues(state, names, issues):
    """
    Keyword Planner numbers from "Searches a month: ..." issues (the
    dashboard's Set button opens them) into settings -> searches_per_month,
    then close them with what was stored. "clear" removes a game's number.
    """
    store = state["settings"].setdefault("searches_per_month", {})
    for issue in issues:
        if not is_volume_issue(issue):
            continue
        fields = actions.form_fields(issue.get("body"))
        game = (fields.get("game") or (issue.get("title") or "").split(":", 1)[-1]).strip()
        value = (fields.get("searches a month") or "").strip()
        key = game.lower()
        if key not in names:
            close_issue(issue, f"“{game}” is not one of the games Discover knows from your video titles, "
                               "so nothing was changed. Use the Set button on the dashboard, which fills in the name.",
                        "not_planned")
            continue
        n = None if value.lower() in CLEAR_WORDS else parse_monthly(value)
        if value.lower() not in CLEAR_WORDS and not n:
            close_issue(issue, f"“{value}” is not a number Discover can read, so nothing was changed. "
                               "Copy Keyword Planner's *Avg. monthly searches*: a range like `10K – 100K`, or `40000`.",
                        "not_planned")
            continue
        for k in [k for k in store if str(k).strip().lower() == key]:
            del store[k]
        if n:
            store[names[key]] = value
            print(f"  {names[key]}: {value} searches a month, issue #{issue.get('number')}")
            close_issue(issue, f"Stored: **{names[key]}** about {n:,.0f} Google searches a month (from “{value}”). "
                               "The dashboard shows it within a few minutes; the other games are compared with "
                               "your numbers on the next daily run.")
        else:
            print(f"  {names[key]}: number removed, issue #{issue.get('number')}")
            close_issue(issue, f"Removed the number for **{names[key]}**.")


# ------------------------------------------------------------------ games and schedule

def game_settings(state, names, keys):
    """The term, category and skip flag per game: hand edits kept, the rest refreshed."""
    games = state["settings"].setdefault("games", {})
    for key in keys:
        entry = games.get(key)
        if entry and entry.get("manual"):
            continue
        games[key] = {"term": names[key].lower(), "cat": trends.GAMES_CAT if key in AMBIGUOUS else None,
                      "skip": bool(NOT_A_GAME.search(key))}
    return games


def schedule(ranked, settings, pulls, today):
    """
    The games due a search: [(key, reason, urgent)]. Urgent (never searched,
    or the term changed) first by rank, then the most overdue.
    """
    due = []
    for rank, key in enumerate(ranked):
        every = TOP_EVERY if rank < TOP_GAMES else NEXT_EVERY
        s, p = settings[key], pulls.get(key)
        if not p:
            due.append((0, rank, key, "never searched"))
        elif p.get("term") != s["term"] or p.get("cat") != s.get("cat"):
            due.append((0, rank, key, "search term changed" if p.get("term") != s["term"] else "category changed"))
        else:
            age = (today - date.fromisoformat(p["date"])).days
            if age >= every:
                due.append((1, -age, key, f"last searched {age} days ago"))
    due.sort()
    return [(key, why, urgent == 0) for urgent, _, key, why in due]


def archive(name, payload, today):
    folder = os.path.join(ARCHIVE_DIR, iso(today))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, slug(name) + ".json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)


def pull(key, s, budget, today):
    got = trends.related_queries(s["term"], DATE_RANGE, cat=s.get("cat"), budget=budget)
    entry = {"date": iso(today), "term": s["term"], "cat": s.get("cat"), "range": DATE_RANGE, **got}
    archive(key, {"game": key, **entry}, today)
    return entry


# ------------------------------------------------------------------ sizes

def mean(values):
    return sum(values) / len(values) if values else 0.0


def size_of(values, game_avg, dates):
    """
    A question's size on the scale it shares with its game. Its level is the
    busier of its three-month average and its last week, so a problem that
    started five days ago counts at today's pace; its share is that level
    against the game's three-month average. A one-off is most of its three
    months in a few days and faded since.
    """
    avg, recent, total = mean(values), mean(values[-RECENT_DAYS:]), sum(values)
    level = max(avg, recent)
    busiest = sorted(range(len(values)), key=lambda i: -values[i])[:SPIKE_DAYS]
    peak = values[busiest[0]] if busiest else 0.0
    spike = bool(total) and sum(values[i] for i in busiest) / total >= SPIKE_SHARE \
        and mean(values[-3:]) < SPIKE_FADED * peak
    return {"avg": round(avg, 2), "recent": round(recent, 2), "level": round(level, 2),
            "share": round(level / game_avg, 4) if game_avg > 0 else None,
            "spike": spike, "peak": dates[busiest[0]] if busiest and total and dates else None}


def measure(key, s, entry, items, budget, today, limit):
    """
    Put the game and its questions on one scale, at most `limit` searches:
    the rising English questions, and the game's top search as the reference
    for the top ones (a top score is a share of that search). Writes "sizes",
    "ref" and "measured" into the pull. Returns the searches spent.
    """
    rising = [e["query"] for e in sorted(items, key=lambda e: (not e["breakout"], -(e["rise"] or 0)))
              if e["kind"] == "rising" and not e["foreign"]]
    has_top = any(e["kind"] == "top" or e["foreign"] for e in items)
    ref = ((entry.get("top") or [{}])[0].get("query") if has_top else None) or None
    queue = [q for q in rising if not ref or q.lower() != ref.lower()]
    sizes, ref_size, spent, runs = {}, None, 0, []
    while (ref and ref_size is None and not runs or queue) and spent < min(limit, SIZE_SEARCHES):
        lead = [ref] if ref and not runs else []
        batch = lead + queue[:SIZE_SLOTS - len(lead)]
        queue = queue[len(batch) - len(lead):]
        got = trends.interest_over_time([s["term"]] + batch, DATE_RANGE, cat=s.get("cat"), budget=budget)
        spent += 1
        series = list(got["series"].values())
        game_avg = mean(series[0]) if series else 0.0
        for i, q in enumerate(batch):
            size = size_of(series[i + 1] if i + 1 < len(series) else [], game_avg, got["dates"])
            if lead and i == 0:
                ref_size = size
                if q.lower() in {r.lower() for r in rising}:
                    sizes[q.lower()] = size
            else:
                sizes[q.lower()] = size
        runs.append({"terms": [s["term"]] + batch, **got})
    if spent or not (rising or ref):
        entry["sizes"], entry["measured"] = sizes, iso(today)
        entry["ref"] = {"query": ref, "share": ref_size["share"]} if ref and ref_size else None
    if runs:
        archive(f"{key}-sizes", {"game": key, "cat": s.get("cat"), "range": DATE_RANGE, "runs": runs}, today)
    return spent


def parse_monthly(value):
    """
    Keyword Planner's monthly searches as one number: 40000, "40K", "1.5M",
    or a range such as "10K-100K" (its geometric middle, about 32K).
    """
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = re.sub(r"(?<=\d)[,\s](?=\d{3}(?!\d))", "", str(value or ""))
    found = []
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([kKmM]?)", text):
        found.append(float(n) * {"k": 1e3, "m": 1e6}.get(unit.lower(), 1))
    found = [n for n in found if n > 0]
    if not found:
        return None
    return math.sqrt(found[0] * found[1]) if len(found) > 1 else found[0]


def known_monthly(state, names):
    """{game: monthly searches} from settings -> searches_per_month (keys matched without case)."""
    raw = state["settings"].setdefault("searches_per_month", {})
    out = {}
    for name, value in raw.items():
        key = str(name).strip().lower()
        n = parse_monthly(value)
        if key in names and n:
            out[key] = n
        elif not key.startswith("_"):
            print(f"  ! searches_per_month: “{name}” is {'not one of your games' if key not in names else 'not a number'}")
    return out


def pick_anchor(known):
    """The game in the middle of those with a Keyword Planner number: the others are compared with it."""
    if not known:
        return None
    ranked = sorted(known, key=lambda k: known[k])
    return ranked[len(ranked) // 2]


def calibration_due(cal, known, ranked, settings, today):
    """
    (anchor, games to compare with it this cycle): every game when the anchor
    changed, else those never compared, compared over CALIBRATE_EVERY days
    ago, or whose search term changed since. Top games first.
    """
    anchor = pick_anchor(known)
    if not anchor:
        return anchor, []
    fresh = cal.get("anchor") == anchor and cal.get("term") == settings[anchor]["term"]
    have = (cal.get("games") or {}) if fresh else {}

    def due(g):
        e = have.get(g)
        return (not e or e.get("term") != settings[g]["term"] or e.get("cat") != settings[g].get("cat")
                or (today - date.fromisoformat(e["date"])).days >= CALIBRATE_EVERY)
    return anchor, [g for g in ranked if g not in known and due(g)]


def calibrate(cal, anchor, games, settings, budget, today, limit):
    """
    Each game against the anchor on one scale, four to a search (a game behind
    a category is compared inside it). Its ratio to the anchor turns shares
    into counts; a game too small to chart beside the anchor gets an upper
    bound. Returns the searches spent.
    """
    s_anchor = settings[anchor]
    if cal.get("anchor") != anchor or cal.get("term") != s_anchor["term"]:
        cal.clear()
    cal.update({"anchor": anchor, "term": s_anchor["term"]})
    cal.setdefault("games", {})
    spent, runs = 0, []
    groups = {}
    for g in games:
        groups.setdefault(settings[g].get("cat"), []).append(g)
    for cat, members in groups.items():
        for i in range(0, len(members), SIZE_SLOTS):
            if spent >= limit or budget.left() <= 0:
                break
            batch = [g for g in members[i:i + SIZE_SLOTS] if settings[g]["term"] != s_anchor["term"]]
            if not batch:
                continue
            got =trends.interest_over_time([s_anchor["term"]] + [settings[g]["term"] for g in batch],
                                            DATE_RANGE, cat=cat, budget=budget)
            spent += 1
            runs.append({"cat": cat, "games": [anchor] + batch, **got})
            series = list(got["series"].values())
            base = mean(series[0]) if series else 0.0
            if base <= 0:
                print(f"  ! {s_anchor['term']} has too little data to anchor {', '.join(batch)}")
                continue
            for j, g in enumerate(batch):
                avg = mean(series[j + 1]) if j + 1 < len(series) else 0.0
                below = avg < MIN_POINTS
                cal["games"][g] = {"ratio": round((MIN_POINTS if below else avg) / base, 5), "below": below,
                                   "term": settings[g]["term"], "cat": cat, "date": iso(today)}
    if spent:
        cal["date"] = iso(today)
        archive("calibration", {"anchor": anchor, "range": DATE_RANGE, "runs": runs}, today)
    return spent


def game_monthly(key, known, cal):
    """(searches a month, upper bound?) for a game, or (None, False) without a baseline."""
    if key in known:
        return known[key], False
    anchor, entry = cal.get("anchor"), (cal.get("games") or {}).get(key)
    if entry and anchor in known:
        return known[anchor] * entry["ratio"], entry["below"]
    return None, False


# ------------------------------------------------------------------ filtering

def questions_for(key, label, pull_entry, titles, own_terms, news, names, dismissed):
    """(every unanswered question, games searched alongside) for one game's latest pull, before sizes."""
    game_words = set(tokens(key)) | {stem(w) for w in tokens(key)}
    name_words = {w for w in tokens(key) if w not in STOP and not w.isdigit()}
    title_words = [(vid, title, words(title, game_words), topic_words(title, game_words)) for vid, title in titles]
    term_words = [words(t, game_words) for t in own_terms]
    news_words = [(n, topic_words(n["title"], game_words) | set(re.findall(r"\d+", n["title"]))) for n in news]
    hidden = {d["item"] for d in dismissed if not d.get("game") or d["game"] == key}
    seen, out, also = set(), [], []

    entries = [(q, "rising") for q in pull_entry.get("rising") or []] + \
              [(q, "top") for q in pull_entry.get("top") or []]
    for q, kind in entries:
        text = q["query"].strip()
        low = text.lower()
        if low in seen or low in hidden or JUNK.search(low):
            continue
        seen.add(low)
        mentioned = game_of(low, names)
        if mentioned != key:
            # Another game: one of yours is no news; any other was searched alongside.
            if mentioned is None and not (set(tokens(low)) & name_words) and len(also) < ALSO_MAX:
                if kind == "rising" or len(also) < 3:
                    also.append({"query": text, "rise": q.get("rise"), "breakout": q.get("breakout", False)})
            continue
        meaning = words(low, game_words)
        foreign = is_foreign(low, key)
        if not meaning - PLATFORM and not foreign:
            continue   # just the game, maybe with a platform or a year
        if meaning and any(meaning <= tw for tw in term_words if tw):
            continue   # people already find you with this search
        if meaning and any(meaning <= tw for _, _, tw, _ in title_words):
            continue   # one of your videos already answers it
        # The closest video shares a word that carries a topic ("rebels"), not just "best" or "win".
        topic = topic_words(low, game_words)
        best = None
        for vid, title, _, tw in title_words:
            shared = topic & tw
            if shared and (best is None or len(shared) > len(best[2])):
                best = (vid, title, shared)
        intent = intent_of(low)
        about = None
        if intent == "news":
            # The Steam post it is about: a shared topic word, and the same number ("season 17").
            numbers = set(re.findall(r"\d+", low)) - set(re.findall(r"\d+", key))
            for n, nw in news_words:
                if topic & nw and numbers <= nw and (about is None or n["date"] > about["date"]):
                    about = {"title": n["title"], "date": n["date"], "url": n.get("url")}
        out.append({
            "query": text, "kind": kind, "intent": intent, "foreign": foreign,
            "rise": q.get("rise"), "breakout": bool(q.get("breakout")), "score": q.get("score"),
            "closest": {"video_id": best[0], "title": best[1], "words": sorted(best[2])} if best else None,
            "steam": about,
        })
    return out, also


def judge(items, entry, monthly, upper):
    """
    Split a game's questions into (shown, small, other languages), each with
    its size: its share of the game's searches and, with a baseline, its
    searches a month (`upper`: the game's count is only an upper bound).
    """
    sizes, ref = entry.get("sizes") or {}, entry.get("ref") or {}
    top_score = {t["query"].lower(): t.get("score") for t in entry.get("top") or []}
    measured = bool(entry.get("measured"))
    shown, small, foreign = [], [], []
    for e in items:
        low = e["query"].lower()
        score = e["score"] if e["kind"] == "top" else top_score.get(low)
        sz = sizes.get(low)
        share = sz["share"] if sz else None
        if share is None and score is not None and ref.get("share") is not None:
            share = ref["share"] * score / 100   # a top score is a share of the game's top search
        count = monthly * share if monthly and share is not None else None
        e.update({"share": round(share, 4) if share is not None else None,
                  "monthly": round(count) if count is not None else None,
                  "upper": bool(upper and count is not None)})
        factor = FOREIGN_FACTOR if e["foreign"] else 1
        why = None
        if e["foreign"] and (score is None or score < FOREIGN_TOP):
            why = "another language"
        elif e["kind"] == "rising" and not e["foreign"]:
            if sz is None:
                why = "not measured" if measured else None
            elif sz.get("level", sz["avg"]) < MIN_POINTS:
                why = "too small to chart"
            elif sz["spike"]:
                why = f"one-off spike{', ' + sz['peak'] if sz.get('peak') else ''}"
        if why is None and count is not None and count < MIN_MONTHLY * factor:
            why = f"{'under' if upper else 'about'} {round(count):,} searches a month"
        elif why is None and (count is None or upper) and share is not None and share < MIN_SHARE * factor:
            why = f"under {MIN_SHARE * factor:.0%} of the game's searches"
        if why is None:
            shown.append(e)
        else:
            side = {"query": e["query"], "why": why, "kind": e["kind"], "rise": e["rise"],
                    "breakout": e["breakout"], "score": score, "share": e["share"], "monthly": e["monthly"]}
            (foreign if e["foreign"] else small).append(side)
    # The biggest first, then breakouts and the biggest rises, then the top searches nobody answers.
    shown.sort(key=lambda e: (e["kind"] != "rising", -(e["share"] if e["share"] is not None else -1),
                              not e["breakout"], -(e["rise"] or 0), -(e["score"] or 0)))
    return shown[:PER_GAME], small[:SIDE_MAX], foreign[:SIDE_MAX]


def carry_first_seen(prev, questions, today):
    """
    The date each question first showed, carried from the last run. A question
    is new for NEW_DAYS after it first showed, but only on a game that was
    searched before: on a game's first search everything would be "new".
    """
    seen = {}
    for card in prev.get("questions") or []:
        for e in card.get("items", []):
            seen[f"{card['game']}:{e['query'].lower()}"] = (e.get("first_seen"), e.get("later", False))
    known = set((prev.get("pulls") or {}).keys())
    for card in questions:
        for e in card["items"]:
            first, later = seen.get(f"{card['game']}:{e['query'].lower()}") or (iso(today), card["game"] in known)
            e["first_seen"], e["later"] = first, later   # later: came up after the game's first search
            e["new"] = later and (today - date.fromisoformat(first)).days < NEW_DAYS


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="show what would be searched; change nothing")
    ap.add_argument("--offline", action="store_true", help="no searches; rebuild from saved pulls")
    ap.add_argument("--max-searches", type=int, default=RUN_MAX, help=f"searches this run (default {RUN_MAX})")
    args = ap.parse_args(argv)

    meta = load_json(os.path.join(DATA_DIR, "videos.json"), {}).get("videos") or {}
    if not meta:
        print("No video metadata yet; nothing to discover.")
        return 0
    now = datetime.now(timezone.utc)
    today = now.date()
    through = data_through()

    prev = load_json(DISCOVER_PATH, {})
    prev_budget = dict(prev.get("budget") or {})
    state = {"settings": prev.get("settings") or {}, "pulls": prev.get("pulls") or {},
             "budget": {k: prev_budget[k] for k in ("cycle", "used", "log") if k in prev_budget},
             "dismissed": prev.get("dismissed") or [], "calibration": prev.get("calibration") or {}}
    health = []

    names = game_names(m.get("title") or "" for m in meta.values())
    games = {vid: game_of(m.get("title"), names) for vid, m in meta.items()}
    views = views_by_game(games)
    settings = game_settings(state, names, names.keys())
    if not args.dry_run:
        # What you asked for on the dashboard: dismissals and Keyword Planner numbers.
        issues = open_issues()
        dismissed_from_issues(state, issues)
        volumes_from_issues(state, names, issues)
    known = known_monthly(state, names)
    watched = sorted((g for g, n in views.items() if n >= MIN_VIEWS and not settings[g].get("skip")),
                     key=lambda g: -views[g])
    ranked = watched[:TOP_GAMES + NEXT_GAMES]
    print(f"Discover: {len(names)} games in your titles, {len(watched)} with {MIN_VIEWS}+ views "
          f"in 28 days, searching the top {len(ranked)}")

    titles_of = {}
    for vid, g in games.items():
        if g and meta[vid].get("title"):
            titles_of.setdefault(g, []).append((vid, meta[vid]["title"]))
    own = own_search_terms(games)
    news = steam_news(ranked)

    def candidates(key):
        """Every unanswered question in the game's latest pull: what a sizing search measures."""
        p = state["pulls"][key]
        return questions_for(key, names[key], p, titles_of.get(key, []), own.get(key, []),
                             news.get(key, []), names, state["dismissed"])

    budget = trends.Budget(state["budget"], today)
    due = schedule(ranked, settings, state["pulls"], today)
    due_keys = {k for k, _, _ in due}
    unmeasured = [k for k in ranked if k in state["pulls"] and k not in due_keys
                  and not state["pulls"][k].get("measured")]
    # Measuring a saved pull is as urgent as a first search: both by rank, then the overdue ones.
    rank_of = {k: i for i, k in enumerate(ranked)}
    work = sorted([(k, why) for k, why, urgent in due if urgent] + [(k, None) for k in unmeasured],
                  key=lambda kv: rank_of[kv[0]]) + [(k, why) for k, why, urgent in due if not urgent]
    cal = state["calibration"]
    anchor, to_calibrate = calibration_due(cal, known, ranked, settings, today)
    have_key = bool(trends.api_key())

    if args.dry_run:
        print(f"  key: {'set' if have_key else 'missing'}; this cycle (from {budget.ledger['cycle']}): "
              f"{budget.ledger.get('used', 0)} of {budget.cap} used; up to {args.max_searches} this run")
        for key, why in work:
            s = settings[key]
            print(f"  · {names[key]:32s} “{s['term']}”{' cat ' + str(s['cat']) if s.get('cat') else ''} "
                  + (f"({why}): 1 pull + up to {SIZE_SEARCHES} sizing" if why
                     else f"(sizes not measured yet): up to {SIZE_SEARCHES} sizing"))
        if anchor:
            print(f"  anchor: {names[anchor]} (~{known[anchor]:,.0f} searches a month); "
                  f"{len(to_calibrate)} game(s) to compare with it, {SIZE_SLOTS} per search, "
                  f"{CALIBRATE_RUN} searches a run, first")
        else:
            print("  no Keyword Planner numbers under settings → searches_per_month: sizes stay shares")
        print(f"  {len(due)} pull(s) and {len(unmeasured)} sizing(s) due; the run stops at {args.max_searches} searches")
        return 0

    spent = 0

    def room():
        return min(args.max_searches - spent, budget.left())

    def failed(what, e):
        print(f"  ! {what}: {e}")
        health.append({"level": "error", "message": f"Google Trends search for {what} failed: {e}"})
        return "401" in str(e) or "Invalid API key" in str(e)

    if args.offline:
        print("  offline: no searches, rebuilding from saved pulls")
    elif not have_key:
        health.append({"level": "warn", "message": "SERPAPI_KEY is not set, so nothing new was searched. "
                       "These are the last saved results."})
    elif (due or unmeasured or to_calibrate) and args.max_searches > 0:
        budget.check_account()
        stop = False
        # The games against the anchor first (a few searches a month turn
        # every share into a count), then each game in turn: its related
        # searches if due, then their sizes.
        if anchor and to_calibrate:
            print(f"  comparing {len(to_calibrate)} game(s) with {names[anchor]}")
            try:
                spent += calibrate(cal, anchor, to_calibrate, settings, budget, today, min(CALIBRATE_RUN, room()))
            except trends.TrendsError as e:
                spent += 1
                stop = failed(f"{names[anchor]} as the anchor", e)
        for key, why in ([] if stop else work):
            if room() <= 0:
                break
            try:
                if why:
                    print(f"  searching {names[key]} ({why})")
                    state["pulls"][key] = pull(key, settings[key], budget, today)
                    spent += 1
                    if room() <= 0:
                        break
                items, _ = candidates(key)
                spent += measure(key, settings[key], state["pulls"][key], items, budget, today, room())
            except trends.TrendsError as e:
                spent += 1
                if failed(names[key], e):
                    stop = True
                    break
        if budget.left() <= 0:
            health.append({"level": "warn", "message": f"This cycle's {budget.cap} searches are used. "
                           "The next cycle starts on the 12th; until then these are the last saved results."})

    # Filter every saved pull again: a video you uploaded since answers its questions now.
    questions, too_small = [], []
    for key in ranked:
        p = state["pulls"].get(key)
        if not p:
            continue
        if not p.get("rising") and not p.get("top"):
            too_small.append(names[key])
            continue
        items, also = candidates(key)
        monthly, upper = game_monthly(key, known, cal)
        shown, small, foreign = judge(items, p, monthly, upper)
        if shown or also or small or foreign:
            questions.append({"game": key, "label": names[key], "term": p["term"], "cat": p.get("cat"),
                              "searched": p["date"], "measured": p.get("measured"),
                              "videos": len(titles_of.get(key, [])), "views_28d": round(views.get(key, 0)),
                              "monthly": round(monthly) if monthly else None, "upper": upper,
                              "items": shown, "small": small, "other_languages": foreign, "also": also})
    carry_first_seen(prev, questions, today)
    # Games with something new first, then the games that bring you the most views.
    questions.sort(key=lambda c: (not any(e["new"] for e in c["items"]), -c["views_28d"]))
    if too_small:
        health.append({"level": "info", "message": "Too little Google data to read for " + ", ".join(too_small) +
                       ". A better search term can help: set it under settings → games in data/discover.json."})
    if not known:
        health.append({"level": "info", "message": "Sizes are shares of each game's own searches. To see searches "
                       "a month, set Keyword Planner numbers for two or three games under Search volumes below."})

    # Every searched game's size, for the dashboard's Search volumes panel (where the Set button is).
    entered = {str(k).strip().lower(): v for k, v in state["settings"]["searches_per_month"].items()}
    volumes = []
    for key in ranked + [k for k in known if k not in ranked]:
        monthly, upper = game_monthly(key, known, cal)
        volumes.append({"game": key, "label": names[key], "views_28d": round(views.get(key, 0)),
                        "entered": entered.get(key) if key in known else None,
                        "monthly": round(monthly) if monthly else None, "upper": upper,
                        "from": "planner" if key in known else "anchor" if monthly else None})

    ledger, acct = budget.ledger, budget.account
    write_json("discover.json", {
        "generated_at": now.isoformat(), "data_through": through,
        "budget": {"cycle": ledger["cycle"], "used": ledger.get("used", 0), "log": ledger.get("log", []),
                   "cap": budget.cap,
                   "next_cycle": iso(trends.next_cycle(date.fromisoformat(ledger["cycle"]))),
                   # SerpApi's own count when it was read this run, else the last one read.
                   "plan_left": acct["left"] if acct else prev_budget.get("plan_left"),
                   "plan_per_cycle": acct["per_cycle"] if acct else prev_budget.get("plan_per_cycle"),
                   "plan_checked": iso(today) if acct else prev_budget.get("plan_checked")},
        "settings": state["settings"], "pulls": state["pulls"], "dismissed": state["dismissed"],
        "calibration": cal,
        "sizes": {"anchor": cal.get("anchor") if cal.get("anchor") in known else None,
                  "anchor_label": names.get(cal.get("anchor")) if cal.get("anchor") in known else None,
                  "known": {names[k]: round(n) for k, n in known.items()}, "calibrated": cal.get("date"),
                  "games": volumes, "min_monthly": MIN_MONTHLY, "min_share": MIN_SHARE,
                  "foreign_top": FOREIGN_TOP, "foreign_factor": FOREIGN_FACTOR},
        "questions": questions, "health": health, "range": DATE_RANGE,
        "schedule": {"ranked": ranked,
                     "due": [k for k, _, _ in due if (state["pulls"].get(k) or {}).get("date") != iso(today)]},
    })
    print(f"  {spent} search(es) this run; {budget.ledger.get('used', 0)} of {budget.cap} this cycle; "
          f"{sum(len(c['items']) for c in questions)} questions across {len(questions)} games, "
          f"{sum(len(c['small']) for c in questions)} small, "
          f"{sum(len(c['other_languages']) for c in questions)} in other languages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
