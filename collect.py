#!/usr/bin/env python3
"""
YouTube Reporting API collector.

Runs unattended (GitHub Actions). On each run it:

  1. Ensures a reporting job exists for every report type in the registry.
     Creating a job also triggers ~30 days of historical backfill.
  2. Lists all available reports for each job.
  3. Skips anything already archived (tracked in data/state.json).
  4. Downloads each new report CSV and writes it as a daily JSON shard.
  5. Rebuilds a compact summary for the dashboard to read.

Why shards: Reporting API reports expire (60 days regular, 30 for historical
backfill). Anything not archived before expiry is permanently lost. One file per
report-type per day means writes never touch existing files, so a failed run can
never corrupt history, and backfill corrections replace exactly one file.

Usage:
    python scripts/collect.py                 # normal daily run
    python scripts/collect.py --create-jobs   # also create missing jobs
    python scripts/collect.py --dry-run       # show what would happen
    python scripts/collect.py --only channel_reach_basic_a1
"""

import argparse
import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import AuthError, Credentials, USER_AGENT
from report_types import CHANNEL_REPORTS, ordered_report_ids, label_for

REPORTING_BASE = "https://youtubereporting.googleapis.com/v1"
DATA_API_BASE = "https://www.googleapis.com/youtube/v3"

# Scripts live in the repository root (flat layout, matching SteamQTPD),
# so the repo root is simply this file's own directory.
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0


# ---------------------------------------------------------------- HTTP helpers

def _safe(creds, text):
    """
    Scrub credentials from any text destined for a log.

    GitHub Actions logs are public on a public repository, and signed report
    downloadUrls are themselves sensitive (they grant access to the data), so
    nothing credential-shaped should ever reach stdout.
    """
    try:
        return creds._redact(str(text))
    except Exception:
        return str(text)


def _request(creds, url, method="GET", body=None, accept_gzip=False):
    """Authorised request with retry on transient failures."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        headers = creds.headers()
        if body is not None:
            headers["Content-Type"] = "application/json"
        if accept_gzip:
            headers["Accept-Encoding"] = "gzip"

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as e:
            detail = _safe(creds, e.read().decode(errors="replace"))
            # 429/5xx are transient; retry with backoff. Other 4xx are not.
            if e.code == 429 or 500 <= e.code < 600:
                last_err = f"HTTP {e.code}: {detail[:300]}"
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                continue
            # Never echo the URL itself: report downloadUrls carry access tokens.
            raise RuntimeError(f"HTTP {e.code} for {_url_label(url)}\n{detail[:600]}") from e
        except urllib.error.URLError as e:
            last_err = _safe(creds, e)
            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
            continue

    raise RuntimeError(
        f"Request failed after {MAX_RETRIES} attempts: {_url_label(url)}\n{last_err}")


def _url_label(url):
    """A loggable description of a URL, with query string stripped."""
    try:
        parts = urllib.parse.urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}{parts.path}"
    except Exception:
        return "(url withheld)"


def _get_json(creds, url):
    return json.loads(_request(creds, url).decode())


# ------------------------------------------------------------------ job control

def list_jobs(creds):
    """All existing reporting jobs, keyed by reportTypeId."""
    jobs = {}
    page_token = ""
    while True:
        url = f"{REPORTING_BASE}/jobs?pageSize=100"
        if page_token:
            url += "&pageToken=" + urllib.parse.quote(page_token)
        payload = _get_json(creds, url)
        for job in payload.get("jobs", []):
            jobs[job["reportTypeId"]] = job["id"]
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            break
    return jobs


def available_report_types(creds):
    """Report types this channel may actually schedule."""
    types = set()
    page_token = ""
    while True:
        url = f"{REPORTING_BASE}/reportTypes?pageSize=100"
        if page_token:
            url += "&pageToken=" + urllib.parse.quote(page_token)
        payload = _get_json(creds, url)
        for rt in payload.get("reportTypes", []):
            if not rt.get("deprecateTime"):
                types.add(rt["id"])
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            break
    return types


def create_job(creds, report_type_id):
    body = {"reportTypeId": report_type_id, "name": label_for(report_type_id)[:100]}
    payload = json.loads(_request(creds, f"{REPORTING_BASE}/jobs",
                                  method="POST", body=body).decode())
    return payload["id"]


def ensure_jobs(creds, wanted_ids, dry_run=False):
    """Create a reporting job for each wanted report type that lacks one."""
    existing = list_jobs(creds)
    try:
        allowed = available_report_types(creds)
    except Exception as e:
        print(f"  ! could not list report types ({e}); attempting all anyway")
        allowed = set(wanted_ids)

    created = {}
    for rid in wanted_ids:
        if rid in existing:
            continue
        if allowed and rid not in allowed:
            print(f"  - {rid}: not available for this channel, skipping")
            continue
        if dry_run:
            print(f"  [dry-run] would create job for {rid}")
            continue
        try:
            job_id = create_job(creds, rid)
            created[rid] = job_id
            print(f"  + created job for {rid} ({label_for(rid)})")
        except Exception as e:
            # One unavailable report must never block the rest.
            print(f"  ! failed to create job for {rid}: {str(e)[:200]}")

    existing.update(created)
    return existing


def list_reports(creds, job_id):
    """Every generated report for a job."""
    reports = []
    page_token = ""
    while True:
        url = f"{REPORTING_BASE}/jobs/{job_id}/reports?pageSize=100"
        if page_token:
            url += "&pageToken=" + urllib.parse.quote(page_token)
        payload = _get_json(creds, url)
        reports.extend(payload.get("reports", []))
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            break
    return reports


# ------------------------------------------------------------------ CSV parsing

def parse_csv(raw_bytes):
    """
    Parse a report CSV into a list of dicts.

    The header row is authoritative. Google explicitly warns that column order
    is not guaranteed and that new metrics may appear as new columns over time,
    so positional access would silently corrupt data.
    """
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        # Skip fully blank rows and normalise numeric-looking values.
        if not any(v for v in row.values()):
            continue
        clean = {}
        for k, v in row.items():
            if k is None:
                continue
            if v is None or v == "":
                clean[k] = None
                continue
            try:
                clean[k] = int(v)
            except ValueError:
                try:
                    clean[k] = float(v)
                except ValueError:
                    clean[k] = v
        rows.append(clean)
    return rows


def report_day(report):
    """The YYYY-MM-DD the report covers (each covers one 24h period)."""
    return report["startTime"][:10]


# ------------------------------------------------------------------ persistence

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"jobs": {}, "archived": {}, "last_run": None, "runs": []}


def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, STATE_PATH)  # atomic; a crash cannot leave a half-written file


def shard_path(report_type_id, day):
    return os.path.join(REPORTS_DIR, report_type_id, f"{day}.json")


def write_shard(report_type_id, day, rows, meta):
    path = shard_path(report_type_id, day)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "report_type": report_type_id,
        "date": day,
        "row_count": len(rows),
        "report_id": meta.get("id"),
        "create_time": meta.get("createTime"),
        "start_time": meta.get("startTime"),
        "end_time": meta.get("endTime"),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)
    return path


# ------------------------------------------------------------------ collection

def collect_report_type(creds, report_type_id, job_id, state, dry_run=False):
    """Download and archive every not-yet-archived report for one job."""
    archived = state["archived"].setdefault(report_type_id, {})

    try:
        reports = list_reports(creds, job_id)
    except Exception as e:
        print(f"  ! {report_type_id}: could not list reports: {str(e)[:200]}")
        return {"new": 0, "replaced": 0, "failed": 1, "skipped": 0}

    if not reports:
        print(f"  · {report_type_id}: no reports generated yet")
        return {"new": 0, "replaced": 0, "failed": 0, "skipped": 0}

    # Backfill reports reuse the same startTime/endTime with a NEW id and a
    # newer createTime. Keep only the newest per day.
    by_day = {}
    for rep in reports:
        day = report_day(rep)
        prev = by_day.get(day)
        if prev is None or rep["createTime"] > prev["createTime"]:
            by_day[day] = rep

    stats = {"new": 0, "replaced": 0, "failed": 0, "skipped": 0}

    for day in sorted(by_day):
        rep = by_day[day]
        seen = archived.get(day)
        # Already have this exact report (same id) -> nothing to do.
        if seen and seen.get("report_id") == rep["id"]:
            stats["skipped"] += 1
            continue
        is_replacement = bool(seen)

        if dry_run:
            print(f"  [dry-run] would fetch {report_type_id} {day}"
                  + (" (backfill replacement)" if is_replacement else ""))
            stats["replaced" if is_replacement else "new"] += 1
            continue

        try:
            raw = _request(creds, rep["downloadUrl"], accept_gzip=True)
            rows = parse_csv(raw)
            write_shard(report_type_id, day, rows, rep)
            archived[day] = {
                "report_id": rep["id"],
                "create_time": rep["createTime"],
                "row_count": len(rows),
            }
            stats["replaced" if is_replacement else "new"] += 1
        except Exception as e:
            print(f"  ! {report_type_id} {day}: {str(e)[:200]}")
            stats["failed"] += 1

    label = f"  · {report_type_id}: "
    parts = []
    if stats["new"]:
        parts.append(f"{stats['new']} new")
    if stats["replaced"]:
        parts.append(f"{stats['replaced']} backfilled")
    if stats["skipped"]:
        parts.append(f"{stats['skipped']} already archived")
    if stats["failed"]:
        parts.append(f"{stats['failed']} FAILED")
    print(label + (", ".join(parts) if parts else "nothing to do"))
    return stats


# ------------------------------------------------------------- video metadata

def fetch_video_metadata(creds, video_ids):
    """
    Titles and publish dates from the Data API.

    Reports contain only video IDs. Note the YouTube API Services Developer
    Policies require stored resource metadata to be deleted or refreshed after
    30 days, so this file is rewritten on every run rather than accumulated.
    """
    meta = {}
    ids = sorted(set(v for v in video_ids if v and v != "NULL"))
    for i in range(0, len(ids), 50):  # Data API caps at 50 ids per call
        chunk = ids[i:i + 50]
        url = (f"{DATA_API_BASE}/videos?part=snippet,statistics,contentDetails"
               f"&id={','.join(chunk)}&maxResults=50")
        try:
            payload = _get_json(creds, url)
        except Exception as e:
            print(f"  ! video metadata chunk failed: {str(e)[:160]}")
            continue
        for item in payload.get("items", []):
            sn = item.get("snippet", {})
            st = item.get("statistics", {})
            meta[item["id"]] = {
                "title": sn.get("title"),
                "published_at": sn.get("publishedAt"),
                "duration": item.get("contentDetails", {}).get("duration"),
                "thumbnail": (sn.get("thumbnails", {}).get("medium", {}) or {}).get("url"),
                "view_count": int(st["viewCount"]) if st.get("viewCount") else None,
                "like_count": int(st["likeCount"]) if st.get("likeCount") else None,
                "comment_count": int(st["commentCount"]) if st.get("commentCount") else None,
            }
    return meta


def fetch_channel_info(creds):
    url = f"{DATA_API_BASE}/channels?part=snippet,statistics&mine=true"
    payload = _get_json(creds, url)
    items = payload.get("items", [])
    if not items:
        return {}
    it = items[0]
    st = it.get("statistics", {})
    return {
        "id": it["id"],
        "title": it.get("snippet", {}).get("title"),
        "subscriber_count": int(st["subscriberCount"]) if st.get("subscriberCount") else None,
        "view_count": int(st["viewCount"]) if st.get("viewCount") else None,
        "video_count": int(st["videoCount"]) if st.get("videoCount") else None,
    }


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--create-jobs", action="store_true",
                    help="create reporting jobs for any report type missing one")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen without writing anything")
    ap.add_argument("--only", action="append", default=None,
                    help="limit to specific report type id(s)")
    ap.add_argument("--skip-metadata", action="store_true",
                    help="skip the Data API video metadata refresh")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    print(f"Collector run at {started.isoformat()}")

    try:
        creds = Credentials.from_env()
        creds.access_token()  # fail fast on bad credentials
    except AuthError as e:
        print("AUTH ERROR\n" + str(e), file=sys.stderr)
        return 1

    wanted = args.only if args.only else ordered_report_ids()
    unknown = [r for r in wanted if r not in CHANNEL_REPORTS]
    if unknown:
        print("Unknown report type(s): " + ", ".join(unknown), file=sys.stderr)
        return 1

    state = load_state()

    print(f"\nEnsuring reporting jobs ({len(wanted)} report types)...")
    if args.create_jobs:
        jobs = ensure_jobs(creds, wanted, dry_run=args.dry_run)
    else:
        jobs = list_jobs(creds)
        missing = [r for r in wanted if r not in jobs]
        if missing:
            print(f"  {len(missing)} report type(s) have no job yet. "
                  "Re-run with --create-jobs to schedule them.")
            for r in missing[:5]:
                print(f"    - {r}")
            if len(missing) > 5:
                print(f"    ... and {len(missing) - 5} more")
    state["jobs"] = jobs

    print(f"\nCollecting reports...")
    totals = {"new": 0, "replaced": 0, "failed": 0, "skipped": 0}
    for rid in wanted:
        job_id = jobs.get(rid)
        if not job_id:
            continue
        s = collect_report_type(creds, rid, job_id, state, dry_run=args.dry_run)
        for k in totals:
            totals[k] += s[k]

    # Refresh video metadata from whatever video IDs we have archived.
    if not args.dry_run and not args.skip_metadata:
        print("\nRefreshing video metadata...")
        video_ids = set()
        reach_dir = os.path.join(REPORTS_DIR, "channel_basic_a3")
        alt_dir = os.path.join(REPORTS_DIR, "channel_reach_basic_a1")
        for d in (reach_dir, alt_dir):
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d))[-90:]:  # recent 90 days is plenty
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        for row in json.load(f).get("rows", []):
                            vid = row.get("video_id")
                            if vid:
                                video_ids.add(vid)
                except Exception:
                    continue
        if video_ids:
            meta = fetch_video_metadata(creds, video_ids)
            try:
                channel = fetch_channel_info(creds)
            except Exception as e:
                print(f"  ! channel info failed: {str(e)[:160]}")
                channel = {}
            out = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "channel": channel,
                "videos": meta,
            }
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = os.path.join(DATA_DIR, "videos.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(out, f, separators=(",", ":"), sort_keys=True)
            os.replace(tmp, os.path.join(DATA_DIR, "videos.json"))
            print(f"  · metadata for {len(meta)} videos")
        else:
            print("  · no video IDs archived yet")

    if not args.dry_run:
        state["last_run"] = started.isoformat()
        state.setdefault("runs", []).append({
            "at": started.isoformat(),
            "new": totals["new"],
            "backfilled": totals["replaced"],
            "failed": totals["failed"],
        })
        state["runs"] = state["runs"][-60:]  # keep a two-month trail
        save_state(state)

    print(f"\nDone. {totals['new']} new, {totals['replaced']} backfilled, "
          f"{totals['skipped']} already archived, {totals['failed']} failed.")

    # Exit non-zero only if everything failed; partial success is normal
    # while jobs are still warming up.
    if totals["failed"] and not (totals["new"] or totals["replaced"] or totals["skipped"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
