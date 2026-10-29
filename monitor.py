#!/usr/bin/env python3
"""
Flag the videos that need attention, for the dashboard's "Needs attention" panel.

YouTube Studio watches new uploads; nothing watches the back catalogue. This
compares each video's last seven complete days with the 28 days before them
and writes the changes worth acting on to data/attention.json:

    rising        older videos picking up views or impressions, with what drove
                  it (search terms, suggesting videos, outside sites)
    falling       established videos losing their traffic, and from where
    ctr_drop      established videos losing thumbnail clicks
    new_uploads   recent uploads against the channel's other uploads at the
                  same age
    reaction      dislike, comment and unsubscribe spikes
    moving_today  same-day jumps in the public view counter, ahead of the two
                  to three days the analytics reports run behind
    topics        search terms, outside sites and other channels' videos
                  sending far more views than usual

Windows end on the same "data through" day as summarize.py, so the panel and
the rest of the dashboard always describe the same days.

Usage:
    python monitor.py
"""

import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_types import CHANNEL_REPORTS
from summarize import DATA_DIR, data_through, iter_shards, num, source_key, write_json

RECENT_DAYS = 7
BASELINE_DAYS = 28
SERIES_DAYS = 56          # sparkline length on the dashboard
BACK_CATALOGUE_AGE = 30   # days since publishing before a video counts as back catalogue
NEW_UPLOAD_DAYS = 28

# Thresholds were calibrated by replaying these rules over every day from late
# July to late October 2026. On a typical day they flag about two rising
# videos, one rising search term and four falling videos; on a busy day (a
# game update, a trailer) up to about 25 rising videos.
RISE_RATIO = 2.0            # recent daily rate at least this multiple of the usual
RISE_MIN_VIEWS = 25         # views in the recent week
RISE_VIEWS_FLOOR = 1.0      # usual views/day counts as at least this
RISE_MIN_IMPRESSIONS = 300
RISE_IMPRESSIONS_FLOOR = 10.0
FALL_MIN_USUAL = 8.0        # usual views/day; smaller videos swing too much
FALL_RATIO = 0.5
CTR_MIN_RECENT_IMPRESSIONS = 1000
CTR_MIN_USUAL_IMPRESSIONS = 2000
CTR_DROP_RATIO = 0.75
# CTR naturally dips when YouTube widens a video's audience; a drop only means
# something while impressions stay roughly level.
CTR_MAX_IMPRESSION_GROWTH = 1.5
TOPIC_RATIO = 3.0
TOPIC_FLOOR = 0.5           # usual views/day counts as at least this
TODAY_MIN = 20              # views/day by the public counter
TODAY_RATIO = 3.0
TODAY_FLOOR = 2.0
COHORT_MIN = 5              # earlier uploads needed for a same-format comparison
SHORTS_MAX_SECONDS = 60     # matches the dashboard's Shorts filter
STALE_RUN_HOURS = 36
STALE_DATA_DAYS = 5

SEARCH, SUGGESTED, EXTERNAL = "5", "7", "9"
# Traffic sources whose details are channel-wide topics: name, minimum recent views.
TOPIC_SOURCES = {SEARCH: ("search", 15), EXTERNAL: ("external", 10), SUGGESTED: ("suggested", 15)}

SCALE = RECENT_DAYS / BASELINE_DAYS   # baseline total -> expected recent total


def iso(d):
    return d.strftime("%Y-%m-%d")


def parse_duration(value):
    """ISO 8601 duration ("PT12M39S") to seconds, or None."""
    if not value or not value.startswith("P"):
        return None
    total, number = 0, ""
    for ch in value[1:]:
        if ch.isdigit():
            number += ch
        elif ch in "DHMS" and number:
            total += int(number) * {"D": 86400, "H": 3600, "M": 60, "S": 1}[ch]
            number = ""
    return total


def rates(recent, baseline):
    """Daily rates for the recent week and the baseline."""
    return {"before": round(baseline / BASELINE_DAYS, 1), "now": round(recent / RECENT_DAYS, 1)}


def ctr(m):
    return round(m["clicks"] / m["impressions"] * 100, 2) if m["impressions"] else None


# ------------------------------------------------------------------ loading

def load_daily(through):
    """Per-video daily totals of every metric the signals use: [video][day][metric]."""
    daily = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for day, rows in iter_shards("channel_basic_a3", until=through):
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
            m["subscribers_gained"] += num(row.get("subscribers_gained"))
            m["subscribers_lost"] += num(row.get("subscribers_lost"))
            m["avg_view_pct_weighted"] += num(row.get("average_view_duration_percentage")) * views
    for day, rows in iter_shards("channel_reach_basic_a1", until=through):
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
    return daily


def window(days, since, until):
    out = defaultdict(float)
    for day, m in days.items():
        if since <= day <= until:
            for k, x in m.items():
                out[k] += x
    return out


def load_traffic(recent_from, baseline_from, through):
    """
    Views by traffic source and by source detail, split into [recent, baseline].

    Returns per-video sources, per-video details, and channel-wide totals per
    (source, detail) for the topic lists.
    """
    sources = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    details = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    topics = defaultdict(lambda: {"totals": [0.0, 0.0], "videos": defaultdict(float)})
    for day, rows in iter_shards("channel_traffic_source_a3", baseline_from, through):
        i = 0 if day >= recent_from else 1
        for row in rows:
            vid = row.get("video_id")
            src = source_key(row)
            views = num(row.get("views"))
            detail = row.get("traffic_source_detail")
            # The collector turns numeric-looking CSV values into numbers, so a
            # search for "2077" arrives as an int. Search terms differ only in
            # case far too often to count separately.
            detail = None if detail is None else str(detail)
            if detail and src == SEARCH:
                detail = detail.lower()
            if vid:
                sources[vid][src][i] += views
                if detail:
                    details[(vid, src)][detail][i] += views
            if detail and src in TOPIC_SOURCES:
                t = topics[(src, detail)]
                t["totals"][i] += views
                if vid and i == 0:
                    t["videos"][vid] += views
    return sources, details, topics


# ------------------------------------------------------------------ signals

def drivers(vid, direction, sources, details):
    """
    The traffic sources behind a rise (direction 1) or a fall (-1), each with
    its top details: search terms, suggesting videos, referring sites.
    """
    found = []
    for src, (r, b) in sources.get(vid, {}).items():
        gain = r - b * SCALE
        if gain * direction >= 1:
            found.append((abs(gain), src, r, b, gain))
    found.sort(reverse=True)
    total = sum(f[0] for f in found)
    out = []
    for size, src, r, b, gain in found[:2]:
        if out and size < 0.2 * total:
            break
        top = []
        for detail, (dr, db) in details.get((vid, src), {}).items():
            dg = dr - db * SCALE
            # Under one view of change is noise, and would show as "+0".
            if dg * direction >= 1:
                top.append((abs(dg), detail, dr, db, dg))
        top.sort(reverse=True)
        out.append({
            "source": src, "gain": round(gain), **rates(r, b),
            "details": [{"detail": d, "gain": round(g), **rates(dr, db)}
                        for _, d, dr, db, g in top[:3]],
        })
    return out


def rising_and_falling(windows, ages, sources, details):
    rising, falling, ctr_drop = [], [], []
    for vid, (r, b) in windows.items():
        age = ages.get(vid)
        if age is None or age < BACK_CATALOGUE_AGE:
            continue
        # Falls and CTR drops are only measured once the whole baseline lies
        # past the launch month: every video decays from its launch spike, and
        # launch CTR is inflated by subscribers clicking through notifications.
        settled = age >= BACK_CATALOGUE_AGE + RECENT_DAYS + BASELINE_DAYS
        base = {
            "video_id": vid,
            "views": rates(r["views"], b["views"]),
            "impressions": rates(r["impressions"], b["impressions"]),
            "ctr": {"before": ctr(b), "now": ctr(r)},
            "gain": round(r["views"] - b["views"] * SCALE),
        }
        views_up = (r["views"] >= RISE_MIN_VIEWS and r["views"] / RECENT_DAYS
                    >= RISE_RATIO * max(b["views"] / BASELINE_DAYS, RISE_VIEWS_FLOOR))
        impressions_up = (r["impressions"] >= RISE_MIN_IMPRESSIONS and r["impressions"] / RECENT_DAYS
                          >= RISE_RATIO * max(b["impressions"] / BASELINE_DAYS, RISE_IMPRESSIONS_FLOOR))
        if views_up or impressions_up:
            rising.append({**base, "trigger": "views" if views_up else "impressions",
                           "drivers": drivers(vid, 1, sources, details)})
        elif (settled and b["views"] / BASELINE_DAYS >= FALL_MIN_USUAL
              and r["views"] / RECENT_DAYS <= FALL_RATIO * b["views"] / BASELINE_DAYS):
            falling.append({**base, "drivers": drivers(vid, -1, sources, details)})

        if (settled and r["impressions"] >= CTR_MIN_RECENT_IMPRESSIONS
                and b["impressions"] >= CTR_MIN_USUAL_IMPRESSIONS and b["clicks"]
                and ctr(r) <= CTR_DROP_RATIO * ctr(b)
                and r["impressions"] / RECENT_DAYS
                <= CTR_MAX_IMPRESSION_GROWTH * b["impressions"] / BASELINE_DAYS):
            ctr_drop.append(base)

    rising.sort(key=lambda e: (-e["gain"], -e["impressions"]["now"]))
    falling.sort(key=lambda e: e["gain"])
    ctr_drop.sort(key=lambda e: -e["impressions"]["now"])
    return rising, falling, ctr_drop


def reactions(windows, ages):
    """Dislike, comment and unsubscribe spikes, in weekly counts (they are small)."""
    out = []
    for vid, (r, b) in windows.items():
        age = ages.get(vid, 0)
        kinds = []
        dislike_rate = r["dislikes"] / max(r["likes"], 1)
        usual_dislike_rate = b["dislikes"] / max(b["likes"], 1)
        if r["dislikes"] >= 3 and dislike_rate >= max(2 * usual_dislike_rate, 0.1):
            kinds.append("dislikes")
        # New videos always draw comments; only an older video's surge is news.
        if (age >= 14 and r["comments"] >= 5
                and r["comments"] / RECENT_DAYS >= 3 * max(b["comments"] / BASELINE_DAYS, 0.2)):
            kinds.append("comments")
        if (r["subscribers_lost"] >= 3 and r["subscribers_lost"] > r["subscribers_gained"]
                and r["subscribers_lost"] / RECENT_DAYS >= 3 * max(b["subscribers_lost"] / BASELINE_DAYS, 0.1)):
            kinds.append("unsubscribes")
        if kinds:
            out.append({
                "video_id": vid, "kinds": kinds,
                "week": {k: round(r[k]) for k in ("likes", "dislikes", "comments",
                                                  "subscribers_gained", "subscribers_lost")},
                "usual_week": {k: round(b[k] * SCALE, 1) for k in ("likes", "dislikes", "comments",
                                                                   "subscribers_gained", "subscribers_lost")},
            })
    out.sort(key=lambda e: -len(e["kinds"]))
    return out


def new_uploads(daily, meta, through, reach_start):
    """
    Each recent upload against the channel's other uploads at the same age.

    "Same age" matters: a three-day-old video compared with lifetime totals
    always looks weak. Each earlier upload is summed over its own first n days,
    where n is how many complete days of data the new one has. Only uploads
    since the reach archive began count, so every one has impressions from day
    one; the comparison uses the same format (Shorts or long-form) when there
    are enough of those.
    """
    end = date.fromisoformat(through)
    published = {}
    for vid, m in meta.items():
        if m.get("published_at"):
            published[vid] = date.fromisoformat(m["published_at"][:10])

    def fmt(vid):
        secs = parse_duration(meta.get(vid, {}).get("duration"))
        return "short" if secs is not None and secs <= SHORTS_MAX_SECONDS else "long"

    def first_days(vid, n):
        p = published[vid]
        return window(daily.get(vid, {}), iso(p), iso(p + timedelta(days=n - 1)))

    def measures(m):
        return {
            "views": m["views"],
            "impressions": m["impressions"],
            "ctr": ctr(m),
            "avg_view_pct": round(m["avg_view_pct_weighted"] / m["views"], 1) if m["views"] else None,
        }

    out = []
    today = datetime.now(timezone.utc).date()
    for vid, p in published.items():
        if p > end:
            # Published after the newest analytics day: nothing to compare yet.
            if (today - p).days <= NEW_UPLOAD_DAYS:
                out.append({"video_id": vid, "pending": True, "format": fmt(vid),
                            "public_views": meta[vid].get("view_count")})
            continue
        n = (end - p).days + 1
        if n > NEW_UPLOAD_DAYS:
            continue
        cohort = [u for u in published if u != vid and published[u] >= reach_start
                  and (end - published[u]).days + 1 >= n]
        same = [u for u in cohort if fmt(u) == fmt(vid)]
        if len(same) >= COHORT_MIN:
            cohort, cohort_format = same, fmt(vid)
        else:
            cohort_format = "all"
        mine = measures(first_days(vid, n))
        others = [measures(first_days(u, n)) for u in cohort]
        compare = {}
        for key, value in mine.items():
            values = [o[key] for o in others if o[key] is not None]
            if value is None or not values:
                compare[key] = {"value": value, "typical": None, "rank": None, "of": len(values) + 1}
                continue
            compare[key] = {
                "value": round(value, 2),
                "typical": round(statistics.median(values), 2),
                # 1 = best of all uploads at this age.
                "rank": 1 + sum(1 for x in values if x > value),
                "of": len(values) + 1,
            }
        out.append({"video_id": vid, "pending": False, "format": fmt(vid), "days": n,
                    "cohort_format": cohort_format, "compare": compare})
    out.sort(key=lambda e: (not e["pending"], e.get("days", 0)))
    return out


def snapshot_movers(windows, ages):
    """Same-day jumps in the public view counter, from the last two snapshots."""
    path = os.path.join(DATA_DIR, "snapshots.json")
    if not os.path.exists(path):
        return [], None, 0
    with open(path, encoding="utf-8") as f:
        days = json.load(f).get("days", {})
    keys = sorted(days)
    if len(keys) < 2:
        return [], None, len(keys)
    a, b = days[keys[-2]], days[keys[-1]]
    hours = (datetime.fromisoformat(b["taken_at"]) - datetime.fromisoformat(a["taken_at"])).total_seconds() / 3600
    if hours <= 0:
        return [], None, len(keys)
    per_day = 24 / hours

    out = []
    for vid, now in b["videos"].items():
        before = a["videos"].get(vid)
        # New uploads move every day; they have their own section.
        if not before or ages.get(vid, 0) < NEW_UPLOAD_DAYS:
            continue
        if now[0] is None or before[0] is None:
            continue
        views = (now[0] - before[0]) * per_day
        r, bl = windows.get(vid, (defaultdict(float), defaultdict(float)))
        usual = max(r["views"] / RECENT_DAYS, bl["views"] / BASELINE_DAYS)
        if views < TODAY_MIN or views < TODAY_RATIO * max(usual, TODAY_FLOOR):
            continue
        delta = lambda i: (now[i] - before[i]) if now[i] is not None and before[i] is not None else None
        out.append({"video_id": vid, "views": {"usual": round(usual, 1), "now": round(views)},
                    "likes": delta(1), "comments": delta(2)})
    out.sort(key=lambda e: -e["views"]["now"])
    return out, {"from": a["taken_at"], "to": b["taken_at"]}, len(keys)


def rising_topics(topics, meta):
    """Search terms, outside sites and other channels' videos sending far more views than usual."""
    out = {name: [] for name, _ in TOPIC_SOURCES.values()}
    for (src, detail), t in topics.items():
        name, minimum = TOPIC_SOURCES[src]
        r, b = t["totals"]
        if r < minimum or r / RECENT_DAYS < TOPIC_RATIO * max(b / BASELINE_DAYS, TOPIC_FLOOR):
            continue
        # The channel's own videos suggesting each other is not a topic.
        if src == SUGGESTED and detail in meta:
            continue
        top = sorted(t["videos"].items(), key=lambda kv: -kv[1])[:3]
        out[name].append({"detail": detail, "gain": round(r - b * SCALE), **rates(r, b),
                          "videos": [{"video_id": v, "views": round(x)} for v, x in top]})
    for entries in out.values():
        entries.sort(key=lambda e: -e["gain"])
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
        if hours > STALE_RUN_HOURS:
            out.append({"level": "error",
                        "message": f"The collector last ran {hours / 24:.1f} days ago. Check the Actions tab; "
                                   "an expired token shows as invalid_grant."})
    runs = state.get("runs") or []
    if runs and runs[-1].get("failed"):
        out.append({"level": "warn",
                    "message": f"The last collector run failed to download {runs[-1]['failed']} report(s). "
                               "The next run retries them."})

    lag = (now.date() - date.fromisoformat(through)).days
    if lag > STALE_DATA_DAYS:
        out.append({"level": "warn",
                    "message": f"The newest analytics are for {through}, {lag} days ago. YouTube normally "
                               "runs two to three days behind."})

    # Report types YouTube offers (recorded by the collector) that have no job.
    offered = set(state.get("offered") or CHANNEL_REPORTS)
    missing = sorted(r for r in CHANNEL_REPORTS if r in offered and r not in state.get("jobs", {}))
    if missing:
        out.append({"level": "info",
                    "message": f"{len(missing)} report type(s) are not being collected yet: {', '.join(missing)}. "
                               "Run the workflow once with create_jobs ticked."})
    if snapshot_days < 2:
        out.append({"level": "info",
                    "message": "Same-day movement appears once the collector has taken view-count "
                               "snapshots on two days."})
    return out


# ------------------------------------------------------------------------ main

def series(days, through):
    """Daily views and impressions for the sparklines, ending on `through`."""
    end = date.fromisoformat(through)
    span = [iso(end - timedelta(days=i)) for i in range(SERIES_DAYS - 1, -1, -1)]
    return {
        "from": span[0],
        "views": [round(days.get(d, {}).get("views", 0)) for d in span],
        "impressions": [round(days.get(d, {}).get("impressions", 0)) for d in span],
    }


def carry_first_seen(groups, topics, through):
    """
    Date each item was first flagged, carried over from the previous run, so the
    dashboard can mark what is new. An item that drops off and comes back later
    starts over.
    """
    seen = {}
    if os.path.exists(os.path.join(DATA_DIR, "attention.json")):
        try:
            with open(os.path.join(DATA_DIR, "attention.json"), encoding="utf-8") as f:
                prev = json.load(f)
            for group in groups:
                for e in prev.get(group, []):
                    seen[f"{group}:{e.get('video_id')}"] = e.get("first_seen")
            for name, entries in prev.get("topics", {}).items():
                for e in entries:
                    seen[f"topic:{name}:{e.get('detail')}"] = e.get("first_seen")
        except Exception as e:
            print(f"  ! could not read the previous attention.json: {str(e)[:120]}")
    for group, entries in groups.items():
        for e in entries:
            e["first_seen"] = seen.get(f"{group}:{e['video_id']}") or through
    for name, entries in topics.items():
        for e in entries:
            e["first_seen"] = seen.get(f"topic:{name}:{e['detail']}") or through


def main():
    meta_path = os.path.join(DATA_DIR, "videos.json")
    if not os.path.exists(meta_path):
        print("No video metadata yet; nothing to monitor.")
        return 0
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f).get("videos", {})

    through = data_through()
    end = date.fromisoformat(through)
    recent_from = iso(end - timedelta(days=RECENT_DAYS - 1))
    baseline_to = iso(end - timedelta(days=RECENT_DAYS))
    baseline_from = iso(end - timedelta(days=RECENT_DAYS + BASELINE_DAYS - 1))
    print(f"Monitoring {recent_from}..{through} against {baseline_from}..{baseline_to}")

    ages = {vid: (end - date.fromisoformat(m["published_at"][:10])).days
            for vid, m in meta.items() if m.get("published_at")}
    daily = load_daily(through)
    windows = {vid: (window(days, recent_from, through), window(days, baseline_from, baseline_to))
               for vid, days in daily.items()}
    sources, details, topic_totals = load_traffic(recent_from, baseline_from, through)
    reach_days = [d for d, _ in iter_shards("channel_reach_basic_a1")]
    reach_start = date.fromisoformat(reach_days[0]) if reach_days else end

    rising, falling, ctr_drop = rising_and_falling(windows, ages, sources, details)
    moving_today, snapshot_span, snapshot_days = snapshot_movers(windows, ages)
    groups = {
        "rising": rising,
        "falling": falling,
        "ctr_drop": ctr_drop,
        "new_uploads": new_uploads(daily, meta, through, reach_start),
        "reaction": reactions(windows, ages),
        "moving_today": moving_today,
    }
    topics = rising_topics(topic_totals, meta)
    carry_first_seen(groups, topics, through)

    referenced = {e["video_id"] for entries in groups.values() for e in entries}
    referenced |= {v["video_id"] for entries in topics.values() for e in entries for v in e["videos"]}
    for e in rising + falling:
        for d in e["drivers"]:
            if d["source"] == SUGGESTED:
                referenced |= {x["detail"] for x in d["details"] if x["detail"] in meta}
    videos = {}
    for vid in sorted(referenced):
        m = meta.get(vid, {})
        videos[vid] = {"title": m.get("title"), "published": (m.get("published_at") or "")[:10] or None,
                       "age_days": ages.get(vid)}

    write_json("attention.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_through": through,
        "recent": {"from": recent_from, "to": through},
        "baseline": {"from": baseline_from, "to": baseline_to},
        "snapshot": snapshot_span,
        "health": health_checks(through, snapshot_days),
        **groups,
        "topics": topics,
        "videos": videos,
        "series": {vid: series(daily[vid], through)
                   for vid in sorted({e["video_id"] for entries in groups.values() for e in entries})
                   if vid in daily},
    })
    for name, entries in groups.items():
        print(f"  · {name}: {len(entries)}")
    for name, entries in topics.items():
        print(f"  · topics/{name}: {len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
