#!/usr/bin/env python3
"""
Flag the videos whose own numbers changed enough to act on, for the
dashboard's "Needs attention" panel.

Every video is compared with itself, never with a channel average, two ways:

  - this week (the last seven complete days) against last week, and against
    the week before for slower climbs. A change counts when it is clearly
    bigger than that video's normal week-to-week swing, still there with the
    week's single biggest day taken out, and still holding over the last
    three days.
  - its level now against its level before a shift: the date its numbers
    moved and stayed moved (a game update on Sep 4 still bringing twice the
    summer views in late October). A shift is listed for as long as last week
    is still clearly away from the old level.

Changes are then sorted by what to do about them:

    packaging     impressions up but CTR down: the reach is there, the clicks are not
    clicks        CTR down while impressions held
    wave          impressions or views up: the topic is waking up
    losing        impressions or views down
    conversation  comments or dislikes well above last week

Three or more videos of one game moving the same way, or a game whose
videos together shifted with at least two of them, become a single game
card. Early signals that are not confirmed yet are listed apart: videos up
three days running, games whose videos spiked together on one day, and
same-day jumps in the public view counter.

Each card carries concrete next steps; actions.py records what was done and
measures whether it helped, and those results are shown next to the steps.
patches.py names the Steam update behind a change, where there is one, and
lists recent patches that touch the topic of an older video.

Writes data/attention.json.

Usage:
    python monitor.py
"""

import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import actions
import patches
from signals import SWING, Z_CLEAR, building_up, ctr_change, ctr_of, shift, weekly_change, z_count
from report_types import CHANNEL_REPORTS
from summarize import DATA_DIR, data_through, iter_shards, num, source_key, write_json

MIN_AGE_DAYS = 21     # launches are YouTube Studio's job; the climb test needs three weeks
SERIES_DAYS = 28      # sparkline length on the dashboard...
SERIES_MAX = 112      # ...stretched back to four weeks before a shift, up to this

GAME_MIN = 3          # videos of one game moving the same way become one game card
GAME_SHIFT_MIN = 2    # ...or this many, when the game as a whole shifted with them
GAME_SHIFT_DAYS = 10  # a video "moved with" its game when it shifted this close to the game's date
FLARE_MIN = 4         # a game "flares" when at least this many of its videos,
FLARE_SHARE = 0.3     # and this share of those with impressions,
FLARE_FACTOR = 3.0    # spike to three times their usual day
FLARE_DAYS = 3        # on the same day, within the last three days
TOPIC_MIN = 10        # views this week before a search term, site or video counts
RISE_TO = {"impressions": 50, "views": 10}     # weekly level a rise must reach
FALL_FROM = {"impressions": 150, "views": 25}  # weekly level a fall must start from
CTR_FROM = 100        # impressions in each week before a CTR change counts
TODAY_MIN = 10        # views/day by the public counter
SHIFT_SETTLE = 60     # days after upload before a video's level means anything (launch decay)
SHIFT_LOOKBACK = 182  # days searched for shifts
SETTLING_DAYS = 91    # within this long of a rise, easing back is the wave settling, not lost reach
STALE_DAYS = 60       # a game's newest video older than this is worth saying
COVERED_MIN = 20      # views over four weeks before a game's Steam updates are followed

SEARCH, BROWSE, SUGGESTED, EXTERNAL = "5", "3", "7", "9"
PLAYLIST_SOURCES = ("14", "18")   # Playlists, Playlist page
TOPIC_SOURCES = {SEARCH: "search", EXTERNAL: "external", SUGGESTED: "suggested"}
METRICS = ("impressions", "views")


def iso(d):
    return d.strftime("%Y-%m-%d")


def span(end, days):
    """The `days` dates ending on `end`, oldest first."""
    return [iso(end - timedelta(days=i)) for i in range(days - 1, -1, -1)]


def days_between(first, last):
    """Every date from `first` to `last` (ISO strings), inclusive."""
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    return span(b, (b - a).days + 1) if b >= a else []


# ------------------------------------------------------------------ loading

def load_daily(through):
    """
    Per-video daily totals of every metric the signals use ([video][day][metric]),
    and the days each metric has data for: a day YouTube never delivered is
    missing, not zero.
    """
    daily = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    covered = {m: set() for m in METRICS}
    for day, rows in iter_shards("channel_basic_a3", until=through):
        covered["views"].add(day)
        for row in rows:
            vid = row.get("video_id")
            if not vid:
                # Channel-level rows: YouTube attributes most unsubscribes to
                # no video at all, so they cannot be pinned on one.
                continue
            m = daily[vid][day]
            views = num(row.get("views"))
            m["views"] += views
            m["likes"] += num(row.get("likes"))
            m["dislikes"] += num(row.get("dislikes"))
            m["comments"] += num(row.get("comments"))
            m["avg_view_pct_weighted"] += num(row.get("average_view_duration_percentage")) * views
    for day, rows in iter_shards("channel_reach_basic_a1", until=through):
        covered["impressions"].add(day)
        for row in rows:
            vid = row.get("video_id")
            if not vid:
                continue
            imp = num(row.get("video_thumbnail_impressions"))
            rate = row.get("video_thumbnail_impressions_ctr")
            m = daily[vid][day]
            m["impressions"] += imp
            # A 0-1 ratio, so clicks = impressions * ctr (see summarize.py).
            if isinstance(rate, (int, float)):
                m["clicks"] += imp * rate
    return daily, covered


def load_sources(report, metric, vids, since, through, this_from=None, topics_from=None):
    """
    Daily totals by traffic source for `vids` ([vid][source][day]), by source
    and detail ([(vid, source)][detail][day]), and the days the report covers.
    With `topics_from`, also channel-wide daily totals per (source, detail)
    from that day on, and this week's totals per video for each of them.
    """
    by_source = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    by_detail = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    topic_daily = defaultdict(lambda: defaultdict(float))
    topic_videos = defaultdict(lambda: defaultdict(float))
    covered = set()
    for day, rows in iter_shards(report, since, through):
        covered.add(day)
        topical = topics_from is not None and day >= topics_from
        for row in rows:
            vid = row.get("video_id")
            if vid not in vids and not topical:
                continue
            src = source_key(row)
            n = num(row.get(metric))
            detail = row.get("traffic_source_detail")
            # Numeric-looking CSV values arrive as numbers (a search for
            # "2077"), and search terms differ only in case far too often.
            detail = None if detail is None else str(detail)
            if detail and detail.strip().lower() in ("unknown", "null"):
                detail = None   # YouTube's placeholder for terms it withholds: no information
            if detail and src == SEARCH:
                detail = detail.lower()
            if vid in vids:
                by_source[vid][src][day] += n
                if detail:
                    by_detail[(vid, src)][detail][day] += n
            if topical and detail and src in TOPIC_SOURCES:
                topic_daily[(src, detail)][day] += n
                if vid and this_from and day >= this_from:
                    topic_videos[(src, detail)][vid] += n
    return by_source, by_detail, covered, topic_daily, topic_videos


# ------------------------------------------------------------------ games

GAME_LEAD = re.compile(r"^(?:let'?s play|lets play|how to|guide:?)\s+", re.I)
GAME_SPLIT = re.compile(r"\s*(?::|\||\s-\s|\s–\s|!|\?)\s*")
SEQUEL = re.compile(r"^(?:\d{1,2}|[ivx]+)$")   # "6" or "ii"; a year is not a sequel
# Opening words that never name a game.
NOT_A_GAME = {"the", "a", "an", "new", "best", "top", "my", "why", "what", "this", "these", "i", "is",
              "how", "all", "every", "only", "full", "first", "free", "gaming", "game", "games", "tips"}


def game_names(titles):
    """
    Game names: how titles start ("Tropico 6: ...", "Whiskerwood: ..."), kept
    when three or more titles mention them anywhere ("How To Skip Taxes in
    Whiskerwood"). Returns {key: display name}, longest first so "tropico 6"
    wins over "tropico" when a title matches both.
    """
    titles = list(titles)
    lows = [t.lower() for t in titles]
    shown = defaultdict(Counter)
    for title in titles:
        lead = GAME_SPLIT.split(GAME_LEAD.sub("", title.strip()))[0].strip()
        words = lead.split()
        if 1 <= len(words) <= 4 and words[0].lower() not in NOT_A_GAME:
            shown[" ".join(words).lower()][" ".join(words)] += 1

    def mentions(key):
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])")
        return sum(1 for t in lows if pattern.search(t))

    def extends(key, other):
        """A DLC, edition or subtitle of `other`; a sequel number ("tropico 6") is a game of its own."""
        if not key.startswith(other + " "):
            return False
        return not SEQUEL.match(key[len(other) + 1:].split()[0])

    keys = [k for k in shown if len(k) >= 4 and mentions(k) >= 3]
    keys = [k for k in keys if not any(extends(k, o) for o in keys if o != k)]
    keys.sort(key=len, reverse=True)
    return {k: shown[k].most_common(1)[0][0] for k in keys}


def game_of(title, names):
    low = (title or "").lower()
    for key in names:
        if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", low):
            return key
    return None


# ------------------------------------------------------------------ signals

def level_days(days, metric, covered, settled, end):
    """(day, value) for the days with data from `settled` (or the lookback) to `end`, for the shift test."""
    first = max(settled, end - timedelta(days=SHIFT_LOOKBACK - 1))
    return [(d, days.get(d, {}).get(metric, 0.0)) for d in days_between(iso(first), iso(end)) if d in covered]


def evaluate(days, end, covered, settled=None):
    """
    Every signal for one video (or a game's videos added up) over the weeks
    ending on `end`. Shifts are looked for from `settled` on; None skips them.
    """
    dates = span(end, 21)
    series = lambda m: [days.get(d, {}).get(m, 0.0) for d in dates]
    sig = {}
    for m in METRICS:
        values = series(m)
        direction, how, z = weekly_change(values, SWING[m])
        weeks = [round(sum(values[:7])), round(sum(values[7:14])), round(sum(values[14:]))]
        base = weeks[0] if how in ("climb", "slide") else weeks[1]
        # Only at a level worth acting on: a rise must reach one, a fall start from one.
        if direction > 0 and weeks[2] < RISE_TO[m] or direction < 0 and base < FALL_FROM[m]:
            direction, how = 0, None
        moved = shift(level_days(days, m, covered[m], settled, end)) if settled else None
        if moved and (moved["now"] < RISE_TO[m] if moved["dir"] > 0 else moved["before"] < FALL_FROM[m]):
            moved = None
        if moved:
            moved["days"] = (end - date.fromisoformat(moved["date"])).days
        sig[m] = {"weeks": weeks, "dir": direction, "how": how, "z": round(z, 1), "base": base,
                  "building": building_up(values[7:], SWING[m]) and sum(values[-3:]) * 7 / 3 >= RISE_TO[m],
                  "shift": moved}
    clicks, imps = series("clicks"), series("impressions")
    direction, z = ctr_change(sum(clicks[14:]), sum(imps[14:]), sum(clicks[7:14]), sum(imps[7:14]))
    if min(sum(imps[14:]), sum(imps[7:14])) < CTR_FROM:
        direction = 0
    last, this, recent = ctr_of(clicks[7:14], imps[7:14]), ctr_of(clicks[14:], imps[14:]), ctr_of(clicks[-3:], imps[-3:])
    # The last three days must agree, as for the counts.
    if direction and (recent is None or last is None or (recent - last) * direction < 0):
        direction = 0
    sig["ctr"] = {"last": last, "this": this, "dir": direction, "z": round(z, 1)}
    for m, minimum in (("comments", 5), ("dislikes", 3)):
        values = series(m)
        w1, w0 = sum(values[7:14]), sum(values[14:])
        up = w0 >= minimum and z_count(w0, w1, SWING[m]) >= Z_CLEAR
        sig[m] = {"last": round(w1), "this": round(w0), "dir": 1 if up else 0}
    return sig


def is_losing(sig, dirs):
    falling = [m for m in METRICS if dirs[m] < 0]
    # Fewer impressions while views still grow is not losing anything.
    return bool(falling) and not (falling == ["impressions"] and sig["views"]["weeks"][2] > sig["views"]["weeks"][1])


def situation(sig):
    imp, views, ctr = sig["impressions"]["dir"], sig["views"]["dir"], sig["ctr"]["dir"]
    if imp > 0 and ctr < 0:
        return "packaging"
    if ctr < 0:
        return "clicks"
    if imp > 0 or views > 0:
        return "wave"
    shifted = {m: (sig[m]["shift"] or {}).get("dir", 0) for m in METRICS}
    if is_losing(sig, {m: sig[m]["dir"] for m in METRICS}):
        # Easing back after a recent rise, still well above where it was, is
        # the wave settling, not reach being lost.
        settling = any(sig[m]["shift"] and sig[m]["shift"]["dir"] > 0 and sig[m]["shift"]["days"] <= SETTLING_DAYS
                       for m in METRICS)
        return "wave" if settling else "losing"
    if sig["comments"]["dir"] > 0 or sig["dislikes"]["dir"] > 0:
        return "conversation"
    # Nothing new this week: a level that moved weeks ago and has not gone back.
    if 1 in shifted.values():
        return "wave"
    if is_losing(sig, shifted):
        return "losing"
    return None


def lead_of(sig, sit):
    """
    The metric a card leads with, and whether this week's change or a shift
    put it there: this week's change in the card's direction first, then a
    shift in it, then any change at all.
    """
    want = -1 if sit in ("clicks", "losing") else 1
    for m in METRICS:
        if sig[m]["dir"] == want:
            return m, "week"
    moved = [m for m in METRICS if (sig[m]["shift"] or {}).get("dir") == want]
    if moved:
        return max(moved, key=lambda m: abs(sig[m]["shift"]["z"])), "shift"
    for m in METRICS:
        if sig[m]["dir"]:
            return m, "week"
    return "views", "week"


def windows(sig, lead, basis, end):
    """The days compared to find what drove a change: (now, before)."""
    if basis == "shift":
        s = sig[lead]["shift"]
        start = date.fromisoformat(s["date"])
        return (days_between(s["date"], iso(end)),
                days_between(iso(max(start - timedelta(days=84), end - timedelta(days=SHIFT_LOOKBACK - 1))),
                             iso(start - timedelta(days=1))))
    back = 14 if sig[lead]["how"] in ("climb", "slide") else 7
    return span(end, 7), span(end - timedelta(days=back), 7)


def drivers(vids, direction, now_days, before_days, by_source, by_detail, covered):
    """
    The traffic sources behind a change, as weekly rates over the two sets of
    days (only the days the source report covers), each with its top details.
    """
    now_days = [d for d in now_days if d in covered]
    before_days = [d for d in before_days if d in covered]
    if not now_days or not before_days:
        return []
    k_now, k_before = 7 / len(now_days), 7 / len(before_days)
    rate = lambda per_day: (sum(per_day.get(d, 0.0) for d in now_days) * k_now,
                            sum(per_day.get(d, 0.0) for d in before_days) * k_before)
    totals = defaultdict(lambda: [0.0, 0.0])
    details = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for vid in vids:
        for src, per_day in by_source.get(vid, {}).items():
            now, before = rate(per_day)
            totals[src][0] += now
            totals[src][1] += before
            for d, per_detail_day in by_detail.get((vid, src), {}).items():
                dn, db = rate(per_detail_day)
                details[src][d][0] += dn
                details[src][d][1] += db
    found = []
    for src, (now, before) in totals.items():
        if (now - before) * direction >= 1:
            found.append((abs(now - before), src, now, before))
    found.sort(reverse=True)
    total = sum(f[0] for f in found)
    out = []
    for size, src, now, before in found[:2]:
        if out and size < 0.2 * total:
            break
        top = sorted(((abs(dn - db), d, dn, db) for d, (dn, db) in details[src].items()
                      if (dn - db) * direction >= 1), reverse=True)[:3]
        out.append({"source": src, "this": round(now), "last": round(before),
                    "details": [{"detail": d, "this": round(dn), "last": round(db)} for _, d, dn, db in top]})
    return out


def first_detail(drv, source):
    for d in drv:
        if d["source"] == source and d["details"]:
            return d["details"][0]["detail"]
    return None


def quoted(text, limit=60):
    text = text or ""
    return "“" + (text if len(text) <= limit else text[:limit - 1].rstrip() + "…") + "”"


def short_date(day):
    d = date.fromisoformat(day)
    return f"{d.strftime('%b')} {d.day}"


def ago(days):
    if days < 60:
        return f"{days} days ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def step(key, text, link="edit"):
    """One next step. `key` names the action (see actions.KINDS) so its result
    can be measured and learned; None for advice that is not an action."""
    return {"key": key, "text": text, "link": link}


def plan_for(sit, sig, drv, newer, game_label, update=None, touched=False):
    """
    Concrete next steps for one video, from what changed and what drove it.
    `update` is the game's Steam update behind the change; `touched`, whether
    it shares a topic with this video.
    """
    term, site = first_detail(drv, SEARCH), first_detail(drv, EXTERNAL)
    main = drv[0]["source"] if drv else None
    ctr = sig["ctr"]
    newer_title = quoted(newer["title"]) if newer else None
    steps = []
    if sit in ("packaging", "clicks"):
        held = "while impressions rose" if sit == "packaging" else "while impressions held"
        steps.append(step("thumbnail", f"Start a Test & Compare with 2–3 new thumbnails: CTR fell from "
                                       f"{ctr['last']}% to {ctr['this']}% {held}."))
        steps.append(step("title", f"Lead the title with “{term}”: that search brings the new impressions."
                          if term else "Rewrite the title around what a new viewer gets from the video."))
        if newer:
            steps.append(step("pinned_comment", f"Pin a comment linking {newer_title}, so the viewers "
                                                "who do click stay with you.", "comments"))
    elif sit == "wave":
        if main == EXTERNAL and site:
            steps.append(step("external", f"Find where {site} links to it and join that conversation.", None))
            steps.append(step("pinned_comment", "Pin a comment welcoming the new visitors, with links "
                                                "to your related videos.", "comments"))
        else:
            if term:
                steps.append(step("description", f"Put “{term}” and close variants in the first lines "
                                                 "of the description: it is what people search for."))
            if newer:
                steps.append(step("end_screen", f"Point the end screen at {newer_title} so the new viewers "
                                                "keep watching."))
            steps.append(step("pinned_comment", f"Pin a comment linking {newer_title}." if newer else
                              "Pin a comment pointing to your playlist on this topic.", "comments"))
            if game_label:
                why = f" after {quoted(update['title'], 70)}" if update else ""
                steps.append(step("follow_up", f"{game_label} is drawing interest again{why}: a new video or "
                                               "Short on it now rides the wave.", None))
    elif sit == "losing":
        if update and touched:
            steps.append(step("title", f"{quoted(update['title'], 70)} ({short_date(update['date'])}) changed what "
                                       "this video covers: refresh the title, description and a pinned comment "
                                       "for the update."))
        if main == SEARCH:
            lost = [d["detail"] for d in drv[0]["details"][:2]]
            steps.append(step("title", "Search traffic fell" + (" for " + ", ".join(f"“{x}”" for x in lost)
                                                                 if lost else "") +
                              ": refresh the title and description with how people search for it now."))
            steps.append(step("tags", "Update the tags to match current searches."))
        elif main in PLAYLIST_SOURCES:
            steps.append(step("playlist", (f"Most of the drop came from playlists: check it is still in, and near "
                                           f"the top of, your {game_label} playlist." if game_label else
                                           "Most of the drop came from playlists: check it is still in, and near "
                                           "the top of, its playlist.")))
        elif main in (BROWSE, SUGGESTED):
            steps.append(step("thumbnail", "YouTube recommends it less: a fresher thumbnail "
                                           "(Test & Compare) can win Home and Suggested back."))
            if newer:
                steps.append(step("end_screen", f"Link to it from the end screen of {newer_title}."))
        else:
            steps.append(step("thumbnail", "Check Reach in Studio for the surface that dropped, then "
                                           "refresh the thumbnail or title.", "analytics"))
        steps.append(step(None, "If it is settling back after a news spike, leave it.", None))
    elif sit == "conversation":
        c = sig["comments"]
        steps.append(step("reply_comments", f"Reply to the new comments: {c['this']} this week, "
                                            f"{c['last']} last week.", "comments"))
        steps.append(step("pinned_comment", "Pin the answer to the most common question.", "comments"))
    return steps


def update_step(label, update, covering):
    """What to do about the Steam update behind a game's change."""
    said = f"{short_date(update['date'])}: {quoted(update['title'], 90)} on Steam."
    if covering:
        return step(None, f"{said} Your {quoted(covering, 50)} touches it: refresh its title, description "
                          "and pinned comment for the update.", None)
    return step(None, f"{said} None of your {label} videos covers it yet: that is the topic.", None)


def game_plan(direction, label, members, newest, term, moved, end, update=None, covering=None):
    """
    Next steps for a whole game card; `moved` is the game's own shift, if any,
    `update` the Steam update behind the change and `covering` the title of
    one of your videos that shares its topic.
    """
    steps = []
    if direction > 0:
        stale = ""
        if newest and newest.get("published"):
            age = (end - date.fromisoformat(newest["published"])).days
            if age > STALE_DAYS:
                stale = (f" Your newest {label} video is {quoted(newest['title'], 40)}, {ago(age)}: "
                         "the new viewers have nothing fresh to move on to.")
        if moved:
            lift = moved["now"] / max(moved["before"], 1)
            steps.append(step("follow_up", f"{label} has run above its old level since {short_date(moved['date'])} "
                                           f"and is still at {lift:.1f}× it: a new video or Short on it now rides "
                                           f"that interest." + stale
                              + (f" People search for “{term}”." if term else ""), None))
            steps.append(update_step(label, update, covering) if update else
                         step(None, f"Look up what happened to {label} around {short_date(moved['date'])}: an "
                                    "update, a sale, a big creator's video. That is the topic to cover.", None))
        else:
            steps.append(step("follow_up", f"{label} is waking up across {len(members)} videos: a new video "
                                           "or Short on it now rides the wave." + stale
                              + (f" People search for “{term}”." if term else ""), None))
            if update:
                steps.append(update_step(label, update, covering))
        if newest:
            steps.append(step("pinned_comment", f"Pin a comment on the biggest risers linking your newest "
                                                f"{label} video, {quoted(newest['title'])}.", None))
        steps.append(step("playlist", f"Put the risers in an up-to-date {label} playlist, and point their "
                                      "end screens at each other.", None))
        lagging = sum(1 for m in members if m["situation"] == "packaging")
        if lagging:
            steps.append(step("thumbnail", f"{lagging} of them {'gets' if lagging == 1 else 'get'} more "
                                           "impressions but fewer clicks: test new thumbnails on those "
                                           "first.", None))
    else:
        steps.append(step(None, "Usually a news cycle ending. Act only if a key earner is on the list.", None))
        steps.append(step("thumbnail", "Refresh the packaging of the biggest losers first.", None))
    return steps


# ------------------------------------------------------------------ early signals

def game_flares(daily, games, end):
    """
    Games whose videos spiked together on one day in the last few days: news,
    an update, a sale. Too short to act on yet, too correlated to be noise.
    """
    by_game = defaultdict(list)
    for vid, g in games.items():
        if g and vid in daily:
            by_game[g].append(vid)
    out = []
    for g, vids in by_game.items():
        if len(vids) < FLARE_MIN:
            continue
        found = None
        for back in range(FLARE_DAYS):
            day = end - timedelta(days=back)
            prior = span(day - timedelta(days=1), 14)
            spiked, active, today, usual_total = [], 0, 0.0, 0.0
            for vid in vids:
                values = [daily[vid].get(d, {}).get("impressions", 0.0) for d in prior]
                if not any(values):
                    continue
                active += 1
                usual = statistics.median(values)
                value = daily[vid].get(iso(day), {}).get("impressions", 0.0)
                today += value
                usual_total += usual
                if value >= FLARE_FACTOR * max(usual, 1) and value - usual >= 5:
                    spiked.append(vid)
            if len(spiked) >= FLARE_MIN and len(spiked) >= FLARE_SHARE * active:
                found = {"game": g, "date": iso(day), "videos": len(spiked), "of": active,
                         "impressions": round(today), "usual": round(usual_total),
                         "video_ids": spiked[:12]}
                break
        if found:
            out.append(found)
    out.sort(key=lambda f: -f["videos"])
    return out


def snapshot_movers(daily, ages, through):
    """
    Same-day jumps in the public view counter, ahead of the analytics. Each
    video's last daily gain is compared with its own earlier daily gains (or,
    until there are three of those, with last week's analytics).
    """
    path = os.path.join(DATA_DIR, "snapshots.json")
    if not os.path.exists(path):
        return [], None, 0
    with open(path, encoding="utf-8") as f:
        days = json.load(f).get("days", {})
    keys = sorted(days)
    if len(keys) < 2:
        return [], None, len(keys)

    def per_day(a, b, vid, i):
        x, y = days[a]["videos"].get(vid), days[b]["videos"].get(vid)
        if not x or not y or x[i] is None or y[i] is None:
            return None
        hours = (datetime.fromisoformat(days[b]["taken_at"])
                 - datetime.fromisoformat(days[a]["taken_at"])).total_seconds() / 3600
        return (y[i] - x[i]) * 24 / hours if hours > 0 else None

    end = date.fromisoformat(through)
    last_week = span(end, 7)
    out = []
    for vid in days[keys[-1]]["videos"]:
        if ages.get(vid, 0) < MIN_AGE_DAYS:
            continue
        now = per_day(keys[-2], keys[-1], vid, 0)
        if now is None or now < TODAY_MIN:
            continue
        earlier = [g for g in (per_day(keys[i - 1], keys[i], vid, 0) for i in range(max(1, len(keys) - 8), len(keys) - 1))
                   if g is not None]
        if len(earlier) >= 3:
            usual = statistics.median(earlier)
        else:
            usual = sum(daily.get(vid, {}).get(d, {}).get("views", 0.0) for d in last_week) / 7
        if z_count(now, usual, SWING["views"]) < Z_CLEAR:
            continue
        out.append({"video_id": vid, "views": {"usual": round(usual, 1), "now": round(now)},
                    "likes": per_day(keys[-2], keys[-1], vid, 1), "comments": per_day(keys[-2], keys[-1], vid, 2)})
    out.sort(key=lambda e: -e["views"]["now"])
    return out, {"from": days[keys[-2]]["taken_at"], "to": days[keys[-1]]["taken_at"]}, len(keys)


def rising_topics(topic_daily, topic_videos, meta, end):
    """Search terms, outside sites and other channels' videos clearly rising week on week."""
    out = {name: [] for name in TOPIC_SOURCES.values()}
    dates = span(end, 21)
    for (src, detail), per_day in topic_daily.items():
        values = [per_day.get(d, 0.0) for d in dates]
        if sum(values[14:]) < TOPIC_MIN:
            continue
        if src == SUGGESTED and detail in meta:
            continue   # the channel's own videos suggesting each other is not a topic
        direction, how, _ = weekly_change(values, SWING["views"])
        if direction <= 0:
            continue
        top = sorted(topic_videos.get((src, detail), {}).items(), key=lambda kv: -kv[1])[:3]
        out[TOPIC_SOURCES[src]].append({
            "detail": detail, "how": how, "last": round(sum(values[7:14])), "this": round(sum(values[14:])),
            "videos": [{"video_id": v, "views": round(x)} for v, x in top]})
    for entries in out.values():
        entries.sort(key=lambda e: -(e["this"] - e["last"]))
    return out


def health_checks(through, snapshot_days):
    out = []
    state = {}
    state_path = os.path.join(DATA_DIR, "state.json")
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    now = datetime.now(timezone.utc)

    last = state.get("last_run")
    if not last:
        out.append({"level": "error", "message": "The collector has no recorded run yet."})
    else:
        hours = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        if hours > 36:
            out.append({"level": "error",
                        "message": f"The collector last ran {hours / 24:.1f} days ago. Check the Actions tab; "
                                   "an expired token shows as invalid_grant."})
    runs = state.get("runs") or []
    if runs and runs[-1].get("failed"):
        out.append({"level": "warn",
                    "message": f"The last collector run failed to download {runs[-1]['failed']} report(s). "
                               "The next run retries them."})
    lag = (now.date() - date.fromisoformat(through)).days
    if lag > 5:
        out.append({"level": "warn",
                    "message": f"The newest analytics are for {through}, {lag} days ago. YouTube normally "
                               "runs two to three days behind."})
    offered = set(state.get("offered") or CHANNEL_REPORTS)
    missing = sorted(r for r in CHANNEL_REPORTS if r in offered and r not in state.get("jobs", {}))
    if missing:
        out.append({"level": "info",
                    "message": f"{len(missing)} report type(s) are not being collected yet: {', '.join(missing)}. "
                               "Run the workflow once with create_jobs ticked."})
    if snapshot_days < 2:
        out.append({"level": "info",
                    "message": "Same-day jumps appear once the collector has taken view-count snapshots "
                               "on two days."})
    return out


# ------------------------------------------------------------------------ main

def carry_first_seen(items, through):
    """
    The date each item was first flagged, carried over from the previous run,
    so the dashboard can mark what is new. An item that drops off and comes
    back later starts over.
    """
    seen = {}
    path = os.path.join(DATA_DIR, "attention.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                prev = json.load(f)
            for e in prev.get("cards", []):
                seen[f"card:{e.get('video_id')}:{e.get('situation')}"] = e.get("first_seen")
            for e in prev.get("games", []):
                seen[f"game:{e.get('game')}:{e.get('direction')}"] = e.get("first_seen")
            for name, entries in prev.get("topics", {}).items():
                for e in entries:
                    seen[f"topic:{name}:{e.get('detail')}"] = e.get("first_seen")
        except Exception as e:
            print(f"  ! could not read the previous attention.json: {str(e)[:120]}")
    for key, item in items:
        item["first_seen"] = seen.get(key) or through


def add_up(daily, vids):
    """One daily series for several videos together."""
    total = defaultdict(lambda: defaultdict(float))
    for vid in vids:
        for day, metrics in daily.get(vid, {}).items():
            for m, x in metrics.items():
                total[day][m] += x
    return total


def shift_dates(sig):
    return [sig[m]["shift"]["date"] for m in METRICS if sig[m]["shift"]]


def main():
    meta_path = os.path.join(DATA_DIR, "videos.json")
    if not os.path.exists(meta_path):
        print("No video metadata yet; nothing to monitor.")
        return 0
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f).get("videos", {})

    through = data_through()
    end = date.fromisoformat(through)
    this_from, last_from = iso(end - timedelta(days=6)), iso(end - timedelta(days=13))
    since = iso(end - timedelta(days=SHIFT_LOOKBACK - 1))
    print(f"Monitoring {this_from}..{through} against {last_from}..{iso(end - timedelta(days=7))}, "
          f"and shifts since {since}")

    published = {vid: date.fromisoformat(m["published_at"][:10]) for vid, m in meta.items() if m.get("published_at")}
    ages = {vid: (end - p).days for vid, p in published.items()}
    settled = {vid: p + timedelta(days=SHIFT_SETTLE) for vid, p in published.items()}
    names = game_names(m.get("title") or "" for m in meta.values())
    games = {vid: game_of(m.get("title"), names) for vid, m in meta.items()}
    newest = {}
    for vid, g in games.items():
        if g and vid in published and (g not in newest or published[vid] > published[newest[g]]):
            newest[g] = vid

    daily, covered = load_daily(through)

    def classify(vid, as_of):
        """The situation a video was in on a given day (for actions.py)."""
        return situation(evaluate(daily[vid], as_of, covered, settled.get(vid))) if vid in daily else None

    # Each video against itself.
    flagged, building = {}, []
    for vid, days in daily.items():
        if ages.get(vid, 0) < MIN_AGE_DAYS:
            continue
        sig = evaluate(days, end, covered, settled.get(vid))
        sit = situation(sig)
        if not sit:
            if sig["impressions"]["building"] or sig["views"]["building"]:
                metric = "impressions" if sig["impressions"]["building"] else "views"
                building.append({"video_id": vid, "metric": metric, "weeks": sig[metric]["weeks"]})
            continue
        lead, basis = lead_of(sig, sit)
        g = games.get(vid)
        newer = None
        if g and newest.get(g) and newest[g] != vid and published[newest[g]] > published.get(vid, end):
            newer = {"video_id": newest[g], "title": meta[newest[g]].get("title")}
        flagged[vid] = {
            "video_id": vid, "situation": sit, "game": g, "signals": sig, "lead": lead, "basis": basis,
            "newer": newer, "flags": [k for k in ("comments", "dislikes") if sig[k]["dir"] > 0],
        }

    # A game's settled videos added up: a shift there, with at least two of
    # its videos shifting the same way around the same date, is the game
    # moving, even when no single video is big enough to show it.
    game_moves = {}
    by_game = defaultdict(list)
    for vid, g in games.items():
        if g and vid in daily and vid in settled and ages.get(vid, 0) >= SHIFT_SETTLE + 42:
            by_game[g].append(vid)
    for g, vids in by_game.items():
        if len(vids) < GAME_SHIFT_MIN:
            continue
        sig = evaluate(add_up(daily, vids), end, covered, max(settled[v] for v in vids))
        moved = max((sig[m]["shift"] for m in ("views", "impressions") if sig[m]["shift"]),
                    key=lambda s: abs(s["z"]), default=None)
        if not moved:
            continue
        day = date.fromisoformat(moved["date"])
        with_it = [v for v in vids if v in flagged and any(
            abs((date.fromisoformat(d) - day).days) <= GAME_SHIFT_DAYS
            for d in shift_dates(flagged[v]["signals"]))
            and (flagged[v]["situation"] == "losing") == (moved["dir"] < 0)]
        if len(with_it) >= GAME_SHIFT_MIN:
            game_moves[(g, moved["dir"])] = {"signals": sig, "shift": moved, "videos": with_it, "of": len(vids)}

    # Who drove each change: traffic sources, read only for what is flagged.
    groups = defaultdict(list)
    for vid, card in flagged.items():
        if card["game"] and card["situation"] in ("wave", "packaging", "losing"):
            groups[(card["game"], -1 if card["situation"] == "losing" else 1)].append(vid)
    for key, move in game_moves.items():
        groups[key] = sorted(set(groups[key]) | set(move["videos"]))
    wanted = set(flagged) | {v for vids in groups.values() for v in vids}
    wanted |= {v for (g, _) in game_moves for v in by_game[g]}
    imp_source, imp_detail, imp_covered, _, _ = load_sources(
        "channel_reach_combined_a1", "video_thumbnail_impressions", wanted, since, through)
    view_source, view_detail, view_covered, topic_daily, topic_videos = load_sources(
        "channel_traffic_source_a3", "views", wanted, since, through, this_from, iso(end - timedelta(days=20)))
    sources = {"impressions": (imp_source, imp_detail, imp_covered),
               "views": (view_source, view_detail, view_covered)}

    # Steam updates for the games on the panel, and for any game still
    # watched enough that an outdated video matters.
    flares = game_flares(daily, games, end)
    month = span(end, 28)
    watched = Counter()
    for vid, g in games.items():
        if g and vid in daily:
            watched[g] += sum(daily[vid].get(d, {}).get("views", 0.0) for d in month)
    keys = {g for g, n in watched.items() if n >= COVERED_MIN}
    keys |= {c["game"] for c in flagged.values() if c["game"]} | {g for g, _ in groups} | {f["game"] for f in flares}
    steam = patches.load(names, keys)
    calendar = datetime.now(timezone.utc).date()
    recent = iso(end - timedelta(days=10))
    videos_of = defaultdict(list)
    for vid, g in games.items():
        if g and meta.get(vid, {}).get("title"):
            videos_of[g].append((vid, meta[vid]["title"]))

    def update_for(g, sig, lead, basis):
        """The Steam update behind a change: next to a shift's date, or since shortly before this week."""
        if basis == "shift":
            return patches.near(steam.get(g), sig[lead]["shift"]["date"])
        return patches.within(steam.get(g), recent, iso(calendar))

    for vid, card in flagged.items():
        sig, sit, lead, basis = card["signals"], card["situation"], card["lead"], card["basis"]
        direction = (sig[lead]["shift"]["dir"] if basis == "shift" else sig[lead]["dir"]) \
            or (-1 if sit in ("clicks", "losing") else 1)
        card["drivers"] = drivers([vid], direction, *windows(sig, lead, basis, end), *sources[lead])
        g = card["game"]
        card["update"] = update_for(g, sig, lead, basis) if g else None
        touched = bool(card["update"] and patches.covered_by(card["update"], names[g], [(vid, meta[vid].get("title"))]))
        card["plan"] = plan_for(sit, sig, card["drivers"], card.pop("newer"), names.get(g) if g else None,
                                card["update"], touched)

    # Three or more videos of one game moving the same way, or the game as a
    # whole shifting with two of them: one game card.
    game_cards, in_game = [], set()
    for (g, direction), vids in groups.items():
        move = game_moves.get((g, direction))
        # As many of its videos going the other way is a mixed bag, not a game moving.
        if not move and (len(vids) < GAME_MIN or len(groups.get((g, -direction), [])) * 2 > len(vids)):
            continue
        members = sorted((flagged[v] for v in vids),
                         key=lambda c: -abs(c["signals"]["impressions"]["weeks"][2] - c["signals"]["impressions"]["weeks"][1]))
        totals = {m: [sum(c["signals"][m]["weeks"][i] for c in members) for i in range(3)] for m in METRICS}
        if move:
            # The whole game, as the shift was measured on it.
            lead = "views" if move["signals"]["views"]["shift"] else "impressions"
            drv = drivers(by_game[g], direction, *windows(move["signals"], lead, "shift", end), *sources[lead])
        else:
            lead, drv = "impressions", []
            for c in members:
                for d in c["drivers"]:
                    if d["source"] == SEARCH:
                        drv.append(d)
        terms = Counter()
        for d in drv:
            if d["source"] == SEARCH:
                for x in d["details"]:
                    terms[x["detail"]] += x["this"] - x["last"]
        term = terms.most_common(1)[0][0] if terms and direction > 0 else None
        newest_video = ({"video_id": newest[g], "title": meta[newest[g]].get("title"),
                         "published": iso(published[newest[g]])} if newest.get(g) else None)
        update = (patches.near(steam.get(g), move["shift"]["date"]) if move
                  else patches.within(steam.get(g), recent, iso(calendar)))
        covering = patches.covered_by(update, names[g], videos_of[g]) if update else []
        game_cards.append({
            "game": g, "label": names[g], "direction": direction, "totals": totals,
            "shift": {"lead": lead, "of": move["of"], "weeks": {m: move["signals"][m]["weeks"] for m in METRICS},
                      "dirs": {m: move["signals"][m]["dir"] for m in METRICS},
                      **{m: move["signals"][m]["shift"] for m in METRICS}} if move else None,
            "drivers": drv if move else [],
            "members": [{"video_id": c["video_id"], "situation": c["situation"],
                         "impressions": c["signals"]["impressions"]["weeks"][1:],
                         "views": c["signals"]["views"]["weeks"][1:],
                         "ctr": [c["signals"]["ctr"]["last"], c["signals"]["ctr"]["this"]],
                         "shift": c["signals"][c["lead"]]["shift"] if c["basis"] == "shift" else None,
                         "lead": c["lead"], "flags": c["flags"]} for c in members],
            "update": update,
            "plan": game_plan(direction, names[g], members, newest_video, term,
                              move["shift"] if move else None, end, update,
                              meta[covering[0][0]].get("title") if covering else None),
        })
        in_game.update(vids)
    game_cards.sort(key=lambda c: (-c["direction"], -len(c["members"])))
    rank = lambda c: abs(c["signals"][c["lead"]]["shift"]["z"] if c["basis"] == "shift" else c["signals"][c["lead"]]["z"])
    cards = sorted((c for v, c in flagged.items() if v not in in_game), key=lambda c: -rank(c))

    for f in flares:
        f["label"] = names[f["game"]]
        f["update"] = patches.near(steam.get(f["game"]), f["date"], before=3, after=1)
    updates = patches.touching(steam, names, videos_of,
                               {v: iso(p) for v, p in published.items()}, calendar)
    today, snapshot_span, snapshot_days = snapshot_movers(daily, ages, through)
    topics = rising_topics(topic_daily, topic_videos, meta, end)

    # The learning loop: record, measure, remember; then say what worked before.
    logged, playbook = actions.update(meta, daily, through, classify)
    for c in cards:
        actions.annotate(c["plan"], c["situation"], playbook)
    for g in game_cards:
        actions.annotate(g["plan"], "wave" if g["direction"] > 0 else "losing", playbook)

    carry_first_seen([(f"card:{c['video_id']}:{c['situation']}", c) for c in cards]
                     + [(f"game:{g['game']}:{g['direction']}", g) for g in game_cards]
                     + [(f"topic:{n}:{e['detail']}", e) for n, es in topics.items() for e in es], through)

    shown = {c["video_id"] for c in cards}
    shown |= {m["video_id"] for g in game_cards for m in g["members"]}
    shown |= {b["video_id"] for b in building} | {t["video_id"] for t in today}
    referenced = set(shown)
    referenced |= {v["video_id"] for es in topics.values() for e in es for v in e["videos"]}
    referenced |= {a["video_id"] for a in logged}
    referenced |= {newest[g] for g in newest}
    referenced |= {v["video_id"] for u in updates for v in u["videos"]}
    videos = {vid: {"title": meta.get(vid, {}).get("title"),
                    "published": (meta.get(vid, {}).get("published_at") or "")[:10] or None,
                    "age_days": ages.get(vid), "game": names.get(games.get(vid)) if games.get(vid) else None}
              for vid in sorted(referenced)}

    def series(vids, mark=None):
        """Daily impressions and views; back to four weeks before a shift, so the turn shows."""
        days = SERIES_DAYS
        if mark:
            days = min(SERIES_MAX, max(days, (end - date.fromisoformat(mark)).days + 29))
        dates = span(end, days)
        out = {"from": dates[0],
               "impressions": [round(sum(daily.get(v, {}).get(d, {}).get("impressions", 0) for v in vids)) for d in dates],
               "views": [round(sum(daily.get(v, {}).get(d, {}).get("views", 0) for v in vids)) for d in dates]}
        if mark:
            out["mark"] = mark
        return out

    def card_mark(vid):
        c = flagged.get(vid)
        return c["signals"][c["lead"]]["shift"]["date"] if c and c["basis"] == "shift" else None

    write_json("attention.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_through": through,
        "this_week": {"from": this_from, "to": through},
        "last_week": {"from": last_from, "to": iso(end - timedelta(days=7))},
        "health": health_checks(through, snapshot_days),
        "cards": cards,
        "games": game_cards,
        "early": {"building": building, "flares": flares, "today": today, "snapshot": snapshot_span},
        "topics": topics,
        "updates": updates,
        "actions": logged,
        "playbook": playbook,
        "videos": videos,
        "series": {vid: series([vid], card_mark(vid)) for vid in sorted(shown)},
        "game_series": {g["game"]: series(by_game[g["game"]] if g["shift"] else [m["video_id"] for m in g["members"]],
                                          g["shift"][g["shift"]["lead"]]["date"] if g["shift"] else None)
                        for g in game_cards},
    })
    counts = Counter(c["situation"] for c in cards)
    shifted = sum(1 for c in cards if c["basis"] == "shift")
    print(f"  · cards: {dict(counts)} ({shifted} from shifts) | games: {len(game_cards)} "
          f"({sum(len(g['members']) for g in game_cards)} videos, {sum(1 for g in game_cards if g['shift'])} from shifts)"
          f" | building: {len(building)} | flares: {len(flares)} | today: {len(today)}"
          f" | topics: {sum(len(e) for e in topics.values())} | updates: {len(updates)} | actions: {len(logged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
