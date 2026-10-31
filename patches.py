"""
Game updates from Steam, for the "Needs attention" panel.

A shift or a flare usually has a cause, and on a game channel it is often a
patch: Whiskerwood's Sep 4 lift was its Nautical Update. For the games the
panel cares about this finds the Steam app (once; kept in data/steam.json)
and its recent announcements, so that

  - a card can name the update behind a change, and say whether any of your
    videos on the game covers it yet, and
  - a patch whose title shares a topic with one of your older videos (a Tax
    Office patch and "How To Skip Taxes") is flagged while the video may
    still give the old advice.

Both Steam endpoints are public and need no key. Without network access the
news saved by the last run is used, and nothing fails.

data/steam.json can be edited by hand: set an app's "appid" (or null for "not
on Steam") and add "manual": true, and the lookup leaves it alone.
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from summarize import DATA_DIR, write_json

STEAM_PATH = os.path.join(DATA_DIR, "steam.json")
SEARCH_URL = "https://store.steampowered.com/api/storesearch/?term={}&l=english&cc=US"
NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={}&count=50&maxlength=1&format=json"
KEEP_DAYS = 180        # news older than this is dropped from steam.json
RECHECK_DAYS = 30      # a game not found on Steam is searched for again after this long
TIME_BUDGET = 90       # seconds of lookups per run; the rest waits for the next run
TOUCH_DAYS = 45        # patches this recent are checked against your videos' topics

PATCH = re.compile(r"\b(?:patch|update|hotfix|hot-fix|version|v\d)", re.I)
# Words that say nothing about a topic: patch-note filler, and video-title filler.
FILLER = set("""
a an the and or of to in on for with without from by at is are be it its this that these your you my we our
new more most all any best top full first only now just here what how why who when which than then also very
update updated updates patch patches hotfix fix fixes fixed bug bugs bugfix optimization optimisation
performance faster improved improvement improvements change changes changed tweak tweaks balance balancing
version release released early access roadmap notes note news announcement dev devlog live stream beta demo
ram fps memory loading load save saves stability crash crashes quality life qol polish misc various
game games gameplay play playing player players guide guides tip tips trick tricks review reviews ultimate
episode part series mission playthrough win walkthrough beginner beginners advanced expert easy hard way ways
video short shorts let lets get got make need know every thing things one two three use using
""".split())


def iso(d):
    return d.strftime("%Y-%m-%d")


def norm(name):
    """A name for matching: lower case, letters and digits only, no leading "the"."""
    name = re.sub(r"^the\s+", "", (name or "").strip().lower())
    return re.sub(r"[^a-z0-9]", "", name)


def stem(word):
    if len(word) > 4 and re.search(r"(?:x|s|ch|sh)es$", word):
        return word[:-2]   # taxes -> tax, batches -> batch
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]   # ships -> ship
    return word


def topic_words(text, skip=()):
    """The words that carry a title's topic."""
    words = (stem(w) for w in re.findall(r"[a-z]+", (text or "").lower()))
    return {w for w in words if len(w) >= 3 and w not in FILLER and w not in skip}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mlmariss-youtube-analyzer"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def find_app(label):
    """The Steam app named `label`: the same name, or that name with a subtitle ("Name: ...")."""
    items = [i for i in fetch(SEARCH_URL.format(urllib.parse.quote(label))).get("items", [])
             if i.get("type") == "app" and i.get("id")]
    want = norm(label)
    for item in items:
        if norm(item.get("name")) == want:
            return {"appid": item["id"], "name": item["name"]}
    for item in items:
        name = item.get("name") or ""
        if len(want) >= 6 and ":" in name and norm(name.split(":")[0]) == want:
            return {"appid": item["id"], "name": name}
    return None


def news_of(appid, today):
    """The developer's announcements for an app over the last KEEP_DAYS days."""
    out, seen = [], set()
    for item in fetch(NEWS_URL.format(appid)).get("appnews", {}).get("newsitems", []):
        # Only the developer's own posts; press articles are not updates.
        if item.get("feedname") != "steam_community_announcements" or not item.get("title"):
            continue
        day = datetime.fromtimestamp(item.get("date", 0), timezone.utc).date()
        if (today - day).days > KEEP_DAYS:
            continue
        title = item["title"].strip()
        url = item.get("url") or ""
        out.append({"title": title, "date": iso(day), "url": url if url.startswith("https://") else None,
                    "patch": "patchnotes" in (item.get("tags") or []) or bool(PATCH.search(title))})
    # A patch reposted under the same title counts from its first post.
    out.sort(key=lambda n: n["date"])
    first = []
    for n in out:
        if n["title"].lower() not in seen:
            seen.add(n["title"].lower())
            first.append(n)
    return first


def load(names, keys, today=None):
    """
    {game key: {"appid", "name", "news": [...]}} for the games in `keys`
    (`names` maps game keys to display names), refreshed from Steam where the
    time budget allows, from data/steam.json otherwise.
    """
    today = today or datetime.now(timezone.utc).date()
    state = {"apps": {}, "news": {}}
    if os.path.exists(STEAM_PATH):
        try:
            with open(STEAM_PATH, encoding="utf-8") as f:
                state.update(json.load(f))
        except Exception as e:
            print(f"  ! could not read steam.json: {str(e)[:120]}")
    apps, news = state["apps"], state["news"]
    started, failures = time.monotonic(), 0
    for key in sorted(keys):
        if time.monotonic() - started > TIME_BUDGET or failures >= 3:
            break   # Steam unreachable or slow: keep what is saved, try again next run
        app = apps.get(key)
        try:
            if app is None or (not app.get("manual") and not app.get("appid")
                               and (today - date.fromisoformat(app.get("checked", "2000-01-01"))).days > RECHECK_DAYS):
                found = find_app(names[key])
                app = apps[key] = {**(found or {"appid": None, "name": None}), "checked": iso(today)}
            if app.get("appid"):
                news[str(app["appid"])] = {"fetched": iso(today), "items": news_of(app["appid"], today)}
        except Exception as e:
            failures += 1
            print(f"  ! Steam lookup for {names[key]} failed: {str(e)[:120]}")
    for appid, entry in news.items():
        entry["items"] = [n for n in entry.get("items", [])
                          if (today - date.fromisoformat(n["date"])).days <= KEEP_DAYS]
    write_json("steam.json", {"apps": dict(sorted(apps.items())), "news": dict(sorted(news.items()))})
    out = {}
    for key in keys:
        app = apps.get(key) or {}
        if app.get("appid"):
            out[key] = {"appid": app["appid"], "name": app.get("name"),
                        "news": (news.get(str(app["appid"])) or {}).get("items", [])}
    return out


def near(game, day, before=4, after=3):
    """The update closest to `day` (patches first), within `before` days ahead of it and `after` past it."""
    if not game or not day:
        return None
    d = date.fromisoformat(day)
    found = [n for n in game["news"]
             if -before <= (date.fromisoformat(n["date"]) - d).days <= after]
    if not found:
        return None
    best = min(found, key=lambda n: (not n["patch"], abs((date.fromisoformat(n["date"]) - d).days)))
    return {k: best[k] for k in ("title", "date", "url")}


def within(game, first, last):
    """The latest patch from `first` to `last`, if any."""
    if not game:
        return None
    found = [n for n in game["news"] if n["patch"] and first <= n["date"] <= last]
    return {k: found[-1][k] for k in ("title", "date", "url")} if found else None


def covered_by(update, label, videos):
    """Your videos on the game whose titles share a topic with the update: [(video_id, words)]."""
    skip = topic_words(label)
    words = topic_words(update["title"], skip)
    out = []
    for vid, title in videos:
        shared = words & topic_words(title, skip)
        if shared:
            out.append((vid, sorted(shared)))
    return out


def touching(games, labels, videos_by_game, published, today):
    """
    Recent patches that share a topic with an older video on the same game:
    the video may now give outdated advice, and the patch is a follow-up topic.
    """
    out = []
    for key, game in games.items():
        for n in game["news"]:
            if not n["patch"] or (today - date.fromisoformat(n["date"])).days > TOUCH_DAYS:
                continue
            older = [(v, t) for v, t in videos_by_game.get(key, []) if published.get(v) and published[v] < n["date"]]
            hits = covered_by(n, labels[key], older)
            if hits:
                out.append({"game": key, "label": labels[key], "title": n["title"], "date": n["date"],
                            "url": n["url"], "videos": [{"video_id": v, "words": w} for v, w in hits]})
    out.sort(key=lambda e: e["date"], reverse=True)
    return out
