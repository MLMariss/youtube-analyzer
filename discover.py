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

What is dropped
    - piracy, shop and spec searches (crack, price, system requirements...)
    - a query that is only the game name and a platform ("tropico 6 ps4")
    - a query whose words all appear in one of your titles on that game
    - a query whose words all appear in a YouTube search term that already
      brought those videos views: people already find you with it
    - anything you dismissed (a "Dismiss: ..." issue, from the dashboard)

What a question shows
    rising: how much it grew against the three months before, or Breakout
    (more than +5000%); top: its share of the game's searches (0-100). Each is
    sorted by intent (problem, how-to, news, topic), carries the video of
    yours that comes closest, and the Steam announcement it is about, if any.
    Queries that name another game ("tropico 5", "frostpunk") are kept apart
    as games searched alongside.

data/discover.json holds the result and two things to edit by hand: under
"settings" -> "games", a game's search "term", its "cat" (8 is Google's Games
category, which keeps "Foundation" the game) or "skip": true, with
"manual": true so the run leaves the entry alone. Raw pulls are archived in
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
RUN_MAX = 3             # searches per daily run; spreads ~40 a cycle over the days
PER_GAME = 8            # questions shown per game
ALSO_MAX = 6            # other games searched alongside, per game
OWN_TERM_MIN = 2        # views a YouTube search term needs before it counts as yours
DATE_RANGE = "today 3-m"
NEW_DAYS = 7            # a question is marked new for this long after it first shows

# Never suggested: piracy, and shop, spec and listing searches.
JUNK = re.compile(
    r"\b(?:crack(?:ed)?|torrent|fitgirl|repack|igg|skidrow|codex|dodi|elamigos|steamunlocked|nosteam|"
    r"empress|apk|free download|download free|cd ?key|keys?|g2a|kinguin|eneba|instant gaming|"
    r"price|cost|sale|discount|cheap|buy|refund|metacritic|reviews?|rating|wiki|fandom|reddit|"
    r"system requirements?|requirements|specs|minimum|install size|file size|gb|trailer|release date|"
    r"download|size)\b", re.I)
# Words that alone say nothing beyond the game: platforms, stores, years.
PLATFORM = {"pc", "ps4", "ps5", "playstation", "xbox", "one", "series", "x", "s", "switch", "nintendo", "mac",
            "macos", "mobile", "android", "ios", "iphone", "steam", "deck", "epic", "gog", "gamepass", "pass",
            "game", "games", "gameplay", "online", "offline", "edition", "remastered", "version", "demo", "vr"}
STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "be", "do", "does",
        "did", "can", "i", "my", "me", "you", "your", "it", "its", "this", "that", "how", "what", "why", "when",
        "where", "which", "who", "there", "at", "by", "from", "as", "if", "vs", "versus"}
YEAR = re.compile(r"^(?:19|20)\d\d$")

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


def dismissed_from_issues(state):
    """
    Add "Dismiss: ..." issues (the dashboard opens them) to the dismissed
    list, then close them with a note: the list in discover.json is the record.
    """
    try:
        batch = actions.github("GET", "/issues?state=open&per_page=100")
    except Exception as e:
        print(f"  ! could not read dismiss issues: {str(e)[:120]}")
        return
    if batch is None:
        return   # no GITHUB_TOKEN: nothing to read
    have = {(d.get("game"), d.get("item")) for d in state["dismissed"]}
    for issue in batch:
        if "pull_request" in issue:
            continue
        title = issue.get("title") or ""
        labels = {label.get("name") for label in issue.get("labels", [])}
        if not title.lower().startswith("dismiss:") and "discover" not in labels:
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
        try:
            actions.github("POST", f"/issues/{issue['number']}/comments",
                           {"body": "Hidden from Discover. To show it again, remove it from "
                                    "`dismissed` in `data/discover.json`."})
            actions.github("PATCH", f"/issues/{issue['number']}", {"state": "closed", "state_reason": "completed"})
        except Exception as e:
            print(f"  ! could not close issue #{issue.get('number')}: {str(e)[:120]}")


# ------------------------------------------------------------------ games and schedule

def game_settings(state, names, keys):
    """The term, category and skip flag per game: hand edits kept, the rest refreshed."""
    games = state["settings"].setdefault("games", {})
    for key in keys:
        entry = games.get(key)
        if entry and entry.get("manual"):
            continue
        label = names[key]
        one_word = len(re.findall(r"[a-z0-9]+", key)) == 1
        games[key] = {"term": label.lower(), "cat": trends.GAMES_CAT if one_word else None,
                      "skip": bool(NOT_A_GAME.search(key))}
    return games


def schedule(ranked, settings, pulls, today):
    """The games due a search, most overdue first: [(key, reason)]."""
    due = []
    for rank, key in enumerate(ranked):
        every = TOP_EVERY if rank < TOP_GAMES else NEXT_EVERY
        s, p = settings[key], pulls.get(key)
        if not p:
            due.append((0, rank, key, "never searched"))
        elif p.get("term") != s["term"] or p.get("cat") != s.get("cat"):
            due.append((0, rank, key, "search term changed"))
        else:
            age = (today - date.fromisoformat(p["date"])).days
            if age >= every:
                due.append((1, -age, key, f"last searched {age} days ago"))
    due.sort()
    return [(key, why) for _, _, key, why in due]


def pull(key, s, budget, today):
    got = trends.related_queries(s["term"], DATE_RANGE, cat=s.get("cat"), budget=budget)
    entry = {"date": iso(today), "term": s["term"], "cat": s.get("cat"), "range": DATE_RANGE, **got}
    folder = os.path.join(ARCHIVE_DIR, iso(today))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, slug(key) + ".json"), "w", encoding="utf-8") as f:
        json.dump({"game": key, **entry}, f, ensure_ascii=False, indent=1, sort_keys=True)
    return entry


# ------------------------------------------------------------------ filtering

def questions_for(key, label, pull_entry, titles, own_terms, news, names, dismissed):
    """(questions, games searched alongside) for one game's latest pull."""
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
        if not meaning - PLATFORM:
            continue   # just the game, maybe with a platform or a year
        if any(meaning <= tw for tw in term_words if tw):
            continue   # people already find you with this search
        if any(meaning <= tw for _, _, tw, _ in title_words):
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
            "query": text, "kind": kind, "intent": intent,
            "rise": q.get("rise"), "breakout": bool(q.get("breakout")), "score": q.get("score"),
            "closest": {"video_id": best[0], "title": best[1], "words": sorted(best[2])} if best else None,
            "steam": about,
        })
    # Breakouts, then the biggest rises, then the top searches nobody answers.
    out.sort(key=lambda e: (e["kind"] != "rising", not e["breakout"], -(e["rise"] or 0), -(e["score"] or 0)))
    return out[:PER_GAME], also


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
             "dismissed": prev.get("dismissed") or []}
    health = []

    names = game_names(m.get("title") or "" for m in meta.values())
    games = {vid: game_of(m.get("title"), names) for vid, m in meta.items()}
    views = views_by_game(games)
    settings = game_settings(state, names, names.keys())
    watched = sorted((g for g, n in views.items() if n >= MIN_VIEWS and not settings[g].get("skip")),
                     key=lambda g: -views[g])
    ranked = watched[:TOP_GAMES + NEXT_GAMES]
    print(f"Discover: {len(names)} games in your titles, {len(watched)} with {MIN_VIEWS}+ views "
          f"in 28 days, searching the top {len(ranked)}")

    budget = trends.Budget(state["budget"], today)
    due = schedule(ranked, settings, state["pulls"], today)
    have_key = bool(trends.api_key())

    if args.dry_run:
        print(f"  key: {'set' if have_key else 'missing'}; this cycle (from {budget.ledger['cycle']}): "
              f"{budget.ledger.get('used', 0)} of {budget.cap} used")
        for i, (key, why) in enumerate(due):
            s = settings[key]
            mark = "→" if i < args.max_searches else " "
            print(f"  {mark} {names[key]:32s} “{s['term']}”{' cat ' + str(s['cat']) if s.get('cat') else ''} ({why})")
        print(f"  {min(len(due), args.max_searches)} search(es) would be spent this run; {len(due)} due in all")
        return 0

    dismissed_from_issues(state)

    spent = 0
    if args.offline:
        print("  offline: no searches, rebuilding from saved pulls")
    elif not have_key:
        health.append({"level": "warn", "message": "SERPAPI_KEY is not set, so nothing new was searched. "
                       "These are the last saved results."})
    elif due and args.max_searches > 0:
        budget.check_account()
        for key, why in due:
            if spent >= args.max_searches:
                break
            if budget.left() <= 0:
                health.append({"level": "warn", "message": f"This cycle's {budget.cap} searches are used. "
                               "The next cycle starts on the 12th; until then these are the last saved results."})
                break
            print(f"  searching {names[key]} ({why})")
            try:
                state["pulls"][key] = pull(key, settings[key], budget, today)
                spent += 1
            except trends.TrendsError as e:
                spent += 1
                print(f"  ! {names[key]}: {e}")
                health.append({"level": "error", "message": f"Google Trends search for {names[key]} failed: {e}"})
                if "401" in str(e) or "Invalid API key" in str(e):
                    break

    # Filter every saved pull again: a video you uploaded since answers its questions now.
    titles_of = {}
    for vid, g in games.items():
        if g and meta[vid].get("title"):
            titles_of.setdefault(g, []).append((vid, meta[vid]["title"]))
    own = own_search_terms(games)
    news = steam_news(ranked)
    questions, too_small = [], []
    for key in ranked:
        p = state["pulls"].get(key)
        if not p:
            continue
        if not p.get("rising") and not p.get("top"):
            too_small.append(names[key])
            continue
        items, also = questions_for(key, names[key], p, titles_of.get(key, []), own.get(key, []),
                                    news.get(key, []), names, state["dismissed"])
        if items or also:
            questions.append({"game": key, "label": names[key], "term": p["term"], "cat": p.get("cat"),
                              "searched": p["date"], "videos": len(titles_of.get(key, [])),
                              "views_28d": round(views.get(key, 0)), "items": items, "also": also})
    carry_first_seen(prev, questions, today)
    # Games with something new first, then the games that bring you the most views.
    questions.sort(key=lambda c: (not any(e["new"] for e in c["items"]), -c["views_28d"]))
    if too_small:
        health.append({"level": "info", "message": "Too little Google data to read for " + ", ".join(too_small) +
                       ". A better search term can help: set it under settings → games in data/discover.json."})

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
        "questions": questions, "health": health, "range": DATE_RANGE,
        "schedule": {"ranked": ranked,
                     "due": [k for k, _ in due if (state["pulls"].get(k) or {}).get("date") != iso(today)]},
    })
    print(f"  {spent} search(es) this run; {budget.ledger.get('used', 0)} of {budget.cap} this cycle; "
          f"{sum(len(c['items']) for c in questions)} questions across {len(questions)} games")
    return 0


if __name__ == "__main__":
    sys.exit(main())
