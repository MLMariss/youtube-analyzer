#!/usr/bin/env python3
"""
Build dashboard-ready JSON from the archived daily shards.

The dashboard must not parse hundreds of shard files in the browser, so this
produces a small set of pre-aggregated files:

    data/summary.json          per-video totals over several windows
    data/daily.json            channel-level daily series
    data/traffic.json          traffic source breakdown per video

Critically, CTR is recomputed as (total clicks / total impressions), never as
an average of daily CTR values. Averaging percentages across days weights a
100-impression day the same as a 100,000-impression day and produces a number
that is simply wrong.

Usage:
    python scripts/summarize.py
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


def build_traffic(since=None):
    """Views by traffic source, per video and channel-wide."""
    per_video = defaultdict(lambda: defaultdict(int))
    channel = defaultdict(int)
    for day, rows in iter_shards("channel_traffic_source_a3", since):
        for row in rows:
            vid = row.get("video_id")
            src = row.get("traffic_source_type") or "UNKNOWN"
            v = num(row.get("views"))
            if vid:
                per_video[vid][src] += v
            channel[src] += v
    return {
        "channel": dict(sorted(channel.items(), key=lambda kv: -kv[1])),
        "videos": {vid: dict(sorted(s.items(), key=lambda kv: -kv[1]))
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

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
