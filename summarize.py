#!/usr/bin/env python3
"""
Build dashboard-ready JSON from the archived daily shards.

The dashboard must not parse hundreds of shard files in the browser, so this
produces a small set of pre-aggregated files:

    data/summary.json          per-video totals over several windows
    data/daily.json            channel-level daily series
    data/traffic.json          per traffic source, per video: views, watch
                               time, average view duration, impressions, CTR
    data/traffic_detail.json   top search terms and suggesting videos per source
    data/devices.json          device type and OS breakdown per video
    data/demographics.json     age and gender breakdown per video

Critically, CTR is recomputed as (total clicks / total impressions), never as
an average of daily CTR values. Averaging percentages across days weights a
100-impression day the same as a 100,000-impression day and produces a number
that is simply wrong.

Usage:
    python summarize.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Scripts live in the repository root (flat layout, matching SteamQTPD),
# so the repo root is simply this file's own directory.
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

WINDOWS = {"7d": 7, "28d": 28, "90d": 90, "365d": 365, "all": None}


def iter_shards(report_type, since=None):
    """Yield (day, rows) for a report type, oldest first."""
    d = os.path.join(REPORTS_DIR, report_type)
    if not os.path.isdir(d):
        return
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        day = fn[:-5]
        if since and day < since:
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        yield day, payload.get("rows", [])


def num(v):
    return v if isinstance(v, (int, float)) else 0


def source_key(row):
    """
    Normalise traffic_source_type into a stable string dict key.

    The collector stores numeric CSV values as ints, so traffic_source_type
    arrives as an int code (e.g. 0, 5, 9). Mixing those int keys with the
    "UNKNOWN" string fallback breaks json.dump(sort_keys=True), which sorts
    keys before coercing them to strings. Coerce to str here so every key is
    the same type. Only a genuinely absent source becomes UNKNOWN -- code 0 is
    a real source, so it must not be swallowed by a falsy check.
    """
    src = row.get("traffic_source_type")
    return "UNKNOWN" if src is None else str(src)


def build_video_totals(since=None):
    """
    Per-video aggregates.

    Reach and activity live in different reports, so they are accumulated
    separately and joined on video_id.
    """
    acc = defaultdict(lambda: {
        "impressions": 0.0, "clicks": 0.0,
        "views": 0, "engaged_views": 0, "watch_time_minutes": 0.0,
        "likes": 0, "dislikes": 0, "comments": 0, "shares": 0,
        "subscribers_gained": 0, "subscribers_lost": 0,
        "avg_view_pct_weighted": 0.0, "avg_view_sec_weighted": 0.0,
        "days": set(),
    })

    # Reach: impressions and CTR.
    for day, rows in iter_shards("channel_reach_basic_a1", since):
        for row in rows:
            vid = row.get("video_id")
            if not vid:
                continue
            imp = num(row.get("video_thumbnail_impressions"))
            ctr = row.get("video_thumbnail_impressions_ctr")
            a = acc[vid]
            a["impressions"] += imp
            # Convert each day's CTR back into clicks so days can be summed,
            # then recompute CTR over the whole window at the end.
            if isinstance(ctr, (int, float)):
                a["clicks"] += imp * (ctr / 100.0)
            a["days"].add(day)

    # Core activity.
    for day, rows in iter_shards("channel_basic_a3", since):
        for row in rows:
            vid = row.get("video_id")
            if not vid:
                continue
            a = acc[vid]
            v = num(row.get("views"))
            a["views"] += v
            a["engaged_views"] += num(row.get("engaged_views"))
            a["watch_time_minutes"] += num(row.get("watch_time_minutes"))
            a["likes"] += num(row.get("likes"))
            a["dislikes"] += num(row.get("dislikes"))
            a["comments"] += num(row.get("comments"))
            a["shares"] += num(row.get("shares"))
            a["subscribers_gained"] += num(row.get("subscribers_gained"))
            a["subscribers_lost"] += num(row.get("subscribers_lost"))
            # Weight retention by views, for the same reason as CTR.
            a["avg_view_pct_weighted"] += num(row.get("average_view_duration_percentage")) * v
            a["avg_view_sec_weighted"] += num(row.get("average_view_duration_seconds")) * v
            a["days"].add(day)

    out = {}
    for vid, a in acc.items():
        views = a["views"]
        out[vid] = {
            "impressions": round(a["impressions"]),
            "ctr": round((a["clicks"] / a["impressions"]) * 100, 3) if a["impressions"] else None,
            "views": views,
            "engaged_views": a["engaged_views"],
            "watch_time_minutes": round(a["watch_time_minutes"], 2),
            "avg_view_percentage": round(a["avg_view_pct_weighted"] / views, 2) if views else None,
            "avg_view_seconds": round(a["avg_view_sec_weighted"] / views, 1) if views else None,
            "likes": a["likes"],
            "dislikes": a["dislikes"],
            "comments": a["comments"],
            "shares": a["shares"],
            "subscribers_gained": a["subscribers_gained"],
            "subscribers_lost": a["subscribers_lost"],
            "days_with_data": len(a["days"]),
        }
    return out


def build_daily_series():
    """Channel-level totals per day."""
    daily = defaultdict(lambda: {
        "impressions": 0.0, "clicks": 0.0, "views": 0,
        "watch_time_minutes": 0.0, "subscribers_gained": 0, "subscribers_lost": 0,
    })

    for day, rows in iter_shards("channel_reach_basic_a1"):
        for row in rows:
            imp = num(row.get("video_thumbnail_impressions"))
            ctr = row.get("video_thumbnail_impressions_ctr")
            daily[day]["impressions"] += imp
            if isinstance(ctr, (int, float)):
                daily[day]["clicks"] += imp * (ctr / 100.0)

    for day, rows in iter_shards("channel_basic_a3"):
        for row in rows:
            daily[day]["views"] += num(row.get("views"))
            daily[day]["watch_time_minutes"] += num(row.get("watch_time_minutes"))
            daily[day]["subscribers_gained"] += num(row.get("subscribers_gained"))
            daily[day]["subscribers_lost"] += num(row.get("subscribers_lost"))

    series = []
    for day in sorted(daily):
        d = daily[day]
        series.append({
            "date": day,
            "impressions": round(d["impressions"]),
            "ctr": round((d["clicks"] / d["impressions"]) * 100, 3) if d["impressions"] else None,
            "views": d["views"],
            "watch_time_minutes": round(d["watch_time_minutes"], 2),
            "subscribers_gained": d["subscribers_gained"],
            "subscribers_lost": d["subscribers_lost"],
        })
    return series


def traffic_acc():
    return {"views": 0, "engaged_views": 0, "watch_time_minutes": 0.0,
            "avd_weighted": 0.0, "impressions": 0.0, "clicks": 0.0,
            "reach_seen": False}


def build_traffic(since=None):
    """
    The marketing-channel table: metrics per traffic source, per video.

    Mirrors Studio's "Traffic source" report, except Studio breaks a single
    video down at a time; this covers every video in one pass.

    Views and watch time come from channel_traffic_source_a3, impressions and
    CTR from channel_reach_combined_a1, joined on traffic_source_type.

    Impressions are null, not zero, for sources YouTube attributes none to
    (External, Direct, Shorts feed, Notifications). A measured zero and an
    unmeasurable quantity must not render identically.
    """
    per_video = defaultdict(lambda: defaultdict(traffic_acc))
    channel = defaultdict(traffic_acc)

    def targets(vid, src):
        out = [channel[src]]
        if vid:
            out.append(per_video[vid][src])
        return out

    for day, rows in iter_shards("channel_traffic_source_a3", since):
        for row in rows:
            src = source_key(row)
            v = num(row.get("views"))
            for a in targets(row.get("video_id"), src):
                a["views"] += v
                a["engaged_views"] += num(row.get("engaged_views"))
                a["watch_time_minutes"] += num(row.get("watch_time_minutes"))
                # Weight duration by views, for the same reason as CTR.
                a["avd_weighted"] += num(row.get("average_view_duration_seconds")) * v

    for day, rows in iter_shards("channel_reach_combined_a1", since):
        for row in rows:
            src = source_key(row)
            imp = num(row.get("video_thumbnail_impressions"))
            ctr = row.get("video_thumbnail_impressions_ctr")
            clicks = imp * (ctr / 100.0) if isinstance(ctr, (int, float)) else 0.0
            for a in targets(row.get("video_id"), src):
                a["reach_seen"] = True
                a["impressions"] += imp
                a["clicks"] += clicks

    def formatted(sources):
        out = {}
        for src, a in sorted(sources.items(), key=lambda kv: -kv[1]["views"]):
            views = a["views"]
            out[src] = {
                "views": views,
                "engaged_views": a["engaged_views"],
                "watch_time_minutes": round(a["watch_time_minutes"], 2),
                "avg_view_seconds": round(a["avd_weighted"] / views, 1) if views else None,
                "impressions": round(a["impressions"]) if a["reach_seen"] else None,
                "ctr": round((a["clicks"] / a["impressions"]) * 100, 3) if a["impressions"] else None,
            }
        return out

    return {
        "channel": formatted(channel),
        "videos": {vid: formatted(s) for vid, s in per_video.items()},
    }


def sorted_desc(counts):
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def build_device_os(since=None):
    """Views by device type and by operating system, per video and channel-wide."""
    dev_video = defaultdict(lambda: defaultdict(int))
    os_video = defaultdict(lambda: defaultdict(int))
    dev_channel = defaultdict(int)
    os_channel = defaultdict(int)

    for day, rows in iter_shards("channel_device_os_a3", since):
        for row in rows:
            vid = row.get("video_id")
            v = num(row.get("views"))
            dev = row.get("device_type") or "UNKNOWN"
            osys = row.get("operating_system") or "UNKNOWN"
            dev_channel[dev] += v
            os_channel[osys] += v
            if vid:
                dev_video[vid][dev] += v
                os_video[vid][osys] += v

    return {
        "channel": {"device": sorted_desc(dev_channel), "os": sorted_desc(os_channel)},
        "videos": {vid: {"device": sorted_desc(dev_video[vid]),
                         "os": sorted_desc(os_video[vid])}
                   for vid in set(dev_video) | set(os_video)},
    }


def views_by_dimension_key(since=None):
    """
    Views from channel_basic_a3, keyed by its full non-metric dimension tuple.

    channel_demographics_a1 carries exactly the same dimensions, so this key
    joins the two reports row for row.
    """
    views = defaultdict(int)
    for day, rows in iter_shards("channel_basic_a3", since):
        for row in rows:
            key = (day, row.get("video_id"), row.get("live_or_on_demand"),
                   row.get("subscribed_status"), row.get("country_code"))
            views[key] += num(row.get("views"))
    return views


def build_demographics(since=None):
    """
    Estimated views by age group and gender, per video and channel-wide.

    The demographics report carries only views_percentage -- never a view count.
    Summing those percentages across days would weight a 10-view day the same as
    a 10,000-view day, so each percentage is converted back into views using the
    matching channel_basic_a3 row before anything is added up. Rows with no
    matching activity row cannot be weighted and are skipped.
    """
    base_views = views_by_dimension_key(since)
    per_video = defaultdict(lambda: defaultdict(float))
    channel = defaultdict(float)

    for day, rows in iter_shards("channel_demographics_a1", since):
        for row in rows:
            vid = row.get("video_id")
            key = (day, vid, row.get("live_or_on_demand"),
                   row.get("subscribed_status"), row.get("country_code"))
            base = base_views.get(key)
            if not base:
                continue
            bucket = "{}/{}".format(row.get("age_group") or "UNKNOWN",
                                    row.get("gender") or "UNKNOWN")
            est = base * (num(row.get("views_percentage")) / 100.0)
            if vid:
                per_video[vid][bucket] += est
            channel[bucket] += est

    def rounded(d):
        return sorted_desc({k: round(v, 1) for k, v in d.items()})

    return {
        "channel": rounded(channel),
        "videos": {vid: rounded(b) for vid, b in per_video.items()},
    }


DETAIL_TOP_N = 15


def build_traffic_detail(since=None, top_n=DETAIL_TOP_N):
    """
    Top traffic_source_detail values per video and source.

    This is the granular layer under the source table: for YT_SEARCH the detail
    is the search term viewers typed, for RELATED_VIDEO the ID of the video that
    suggested this one, for EXT_URL the referring domain.

    Capped at the top values by views per (video, source) so 531 videos of
    long-tail search terms stay small enough to ship to a browser.
    """
    per_video = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    channel = defaultdict(lambda: defaultdict(int))

    for day, rows in iter_shards("channel_traffic_source_a3", since):
        for row in rows:
            detail = row.get("traffic_source_detail")
            if not detail:
                continue
            src = source_key(row)
            vid = row.get("video_id")
            v = num(row.get("views"))
            channel[src][detail] += v
            if vid:
                per_video[vid][src][detail] += v

    def top(counts):
        return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:top_n])

    return {
        "channel": {src: top(d) for src, d in channel.items()},
        "videos": {vid: {src: top(d) for src, d in s.items()}
                   for vid, s in per_video.items()},
    }


def cutoff(days):
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def write_json(name, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)
    size = os.path.getsize(path)
    print(f"  wrote {name} ({size:,} bytes)")


def main():
    if not os.path.isdir(REPORTS_DIR):
        print("No archived reports yet; nothing to summarise.")
        return 0

    print("Building summaries...")

    videos_meta = {}
    meta_path = os.path.join(DATA_DIR, "videos.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            videos_meta = json.load(f)

    windows = {}
    for name, days in WINDOWS.items():
        windows[name] = build_video_totals(since=cutoff(days))
        print(f"  · window {name}: {len(windows[name])} videos")

    write_json("summary.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel": videos_meta.get("channel", {}),
        "windows": windows,
        "video_meta": videos_meta.get("videos", {}),
    })

    write_json("daily.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "series": build_daily_series(),
    })

    write_json("traffic.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_time": build_traffic(),
        "last_90d": build_traffic(since=cutoff(90)),
    })

    write_json("devices.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_time": build_device_os(),
        "last_90d": build_device_os(since=cutoff(90)),
    })

    write_json("demographics.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_time": build_demographics(),
        "last_90d": build_demographics(since=cutoff(90)),
    })

    write_json("traffic_detail.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_time": build_traffic_detail(),
        "last_90d": build_traffic_detail(since=cutoff(90)),
    })

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
