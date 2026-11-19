"""
The hourly edit watcher, separate from the daily collector.

Each run:
  1. reads the action log first: what you saved with the dashboard's
     "Log action", kept in a Google Sheet behind a small Apps Script web app
     (docs/action-log.gs). Videos named in new entries are checked first,
     including uploads too new to be in videos.json yet;
  2. fingerprints every video's title, description and tags (Data API,
     1 quota unit per 50 videos) and thumbnail (the public image, no quota);
  3. compares them with the last check and records what changed, and
     between which two checks.

What the last check saw is kept in .watch/state.json, which the workflow
carries from run to run in the Actions cache, not in git. Only
data/edits.json is committed, and it changes only when a video was edited
or the log changed, so most hours commit nothing. actions.py reads it in
the daily run.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from actions import SITUATIONS, VIDEO_ID, kinds_of
from auth import AuthError, Credentials, USER_AGENT
from collect import DATA_DIR, REPO_ROOT, fetch_video_metadata, fingerprint, fingerprint_thumbnails

EDITS_PATH = os.path.join(DATA_DIR, "edits.json")
VIDEOS_PATH = os.path.join(DATA_DIR, "videos.json")
STATE_PATH = os.path.join(REPO_ROOT, ".watch", "state.json")
KEEP_DAYS = 30
PARTS = ("title", "description", "tags", "thumbnail")   # the order of actions.FINGERPRINTED
# YouTube's reports count days in Pacific time, so an edit is dated by that clock.
REPORT_TZ = ZoneInfo("America/Los_Angeles")


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, value, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, **kw)
    os.replace(tmp, path)


# ------------------------------------------------------------------ the action log

def read_log(url, key):
    """Every row of the action log. POST keeps the key out of the URL."""
    body = json.dumps({"key": key, "action": "list"}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "text/plain;charset=utf-8", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "the log refused the request")
    return payload.get("rows") or []


def parse_log(rows):
    """Rows as actions: the video, what was done, the day it went live."""
    out = []
    for row in rows:
        found = VIDEO_ID.search(str(row.get("video") or ""))
        kinds = kinds_of(str(row.get("what") or ""))
        day = re.search(r"\d{4}-\d{2}-\d{2}", str(row.get("date") or "")) or \
            re.search(r"\d{4}-\d{2}-\d{2}", str(row.get("logged_at") or ""))
        if not row.get("id") or not found or not kinds or not day:
            print(f"  ! log row {row.get('id') or '?'} names no video, action or date; left out")
            continue
        situation = str(row.get("situation") or "").strip().lower()
        out.append({
            "id": str(row["id"]), "video_id": found.group(1), "kinds": kinds, "date": day.group(0),
            "situation": situation if situation in SITUATIONS else None,
            "notes": str(row.get("notes") or "")[:280] or None,
            "logged_at": str(row.get("logged_at") or "") or None,
        })
    return sorted(out, key=lambda a: (a["logged_at"] or "", a["id"]))


# ------------------------------------------------------------------ edits

def report_day(stamp):
    return datetime.fromisoformat(stamp).astimezone(REPORT_TZ).strftime("%Y-%m-%d")


def change(video_id, kinds, since, at):
    """An edit made after `since` (the last check that showed the old version) and
    seen at `at`. It is dated by `since`: a new thumbnail can take a while to reach
    the image servers, so the earlier end is the closer one."""
    return {"video_id": video_id, "kinds": kinds, "since": since, "at": at, "date": report_day(since or at)}


def compare(meta, state, now):
    """Fingerprint `meta` against the last check, update `state`, return the changes."""
    videos, pending = state.setdefault("videos", {}), state.setdefault("pending", {})
    out = []
    for vid, m in meta.items():
        new = [fingerprint(m["title"]) if m.get("title") is not None else None,
               m.get("description_hash"), m.get("tags_hash"), m.get("thumbnail_hash")]
        known = videos.get(vid)
        if not known:
            videos[vid] = {"fp": new, "seen": now}   # first sight: nothing to compare with
            continue
        old, since = known["fp"], known["seen"]
        # A part that could not be read keeps its last value and never counts as a change.
        fp = [n if n is not None else o for o, n in zip(old, new)]
        text = [p for i, p in enumerate(PARTS[:3]) if old[i] and new[i] and old[i] != new[i]]
        if text:
            out.append(change(vid, text, since, now))
        # An image can come back re-encoded once: a new thumbnail counts only when
        # the next check still shows it.
        thumb, wait = new[3], pending.get(vid)
        fp[3] = old[3] or thumb
        if thumb and old[3] and thumb != old[3]:
            if wait and wait["hash"] == thumb:
                out.append(change(vid, ["thumbnail"], wait["since"], wait["at"]))
                fp[3] = thumb
                del pending[vid]
            elif wait:
                wait["hash"] = thumb   # changed again before it settled; it began when first seen
            else:
                pending[vid] = {"hash": thumb, "since": since, "at": now}
        elif thumb:
            pending.pop(vid, None)
        videos[vid] = {"fp": fp, "seen": now}
    return out


# ------------------------------------------------------------------------ main

def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = now.isoformat()
    print(f"Edit watcher run at {stamp}")
    try:
        creds = Credentials.from_env()
        creds.access_token()
    except AuthError as e:
        print("AUTH ERROR\n" + str(e), file=sys.stderr)
        return 1

    edits = load(EDITS_PATH, {"changes": [], "logs": []})
    state = load(STATE_PATH, {})

    # 1. The action log, first.
    logs = edits.get("logs", [])
    url, key = os.environ.get("ACTION_LOG_URL", "").strip(), os.environ.get("ACTION_LOG_KEY", "").strip()
    if url and key:
        try:
            logs = parse_log(read_log(url, key))
            print(f"  · action log: {len(logs)} {'entry' if len(logs) == 1 else 'entries'}")
        except Exception as e:
            print(f"  ! could not read the action log, keeping the last copy: {type(e).__name__}: {str(e)[:160]}")
    else:
        print("  · ACTION_LOG_URL or ACTION_LOG_KEY not set: the action log is not read")
    before = {a["id"] for a in edits.get("logs", [])}
    first = list(dict.fromkeys(a["video_id"] for a in logs if a["id"] not in before))

    # 2. Every video, those just logged first.
    ids = list(load(VIDEOS_PATH, {}).get("videos", {}))
    rest = [v for v in ids if v not in first]
    meta = {}
    for batch in (first, rest):
        if batch:
            got = fetch_video_metadata(creds, batch)
            fingerprint_thumbnails(got)
            meta.update(got)
    if not state.get("videos"):
        print("  · no earlier check to compare with: this run sets the baseline")

    # 3. What changed since the last check.
    found = compare(meta, state, stamp)
    for c in found:
        print(f"  · {c['video_id']}: {', '.join(c['kinds'])} changed (dated {c['date']})")
    oldest = (now - timedelta(days=KEEP_DAYS)).isoformat()
    changes = [c for c in edits.get("changes", []) + found if c["at"] > oldest]

    save(EDITS_PATH, {"changes": sorted(changes, key=lambda c: (c["at"], c["video_id"])), "logs": logs}, indent=1)
    state["checked_at"] = stamp
    save(STATE_PATH, state, separators=(",", ":"))
    print(f"  · checked {len(meta)} of {len(set(ids) | set(first))} videos; {len(found)} new changes; "
          f"{len(state.get('pending', {}))} thumbnails waiting for a second look")
    return 0


if __name__ == "__main__":
    sys.exit(main())
