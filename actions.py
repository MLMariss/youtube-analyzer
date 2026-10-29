"""
The learning loop: what was done to a video, and whether it helped.

    A  notice    monitor.py flags a change and suggests what to do
    B  act       you log what you did: the dashboard's "Log action" opens a
                 pre-filled GitHub issue. The collector also notices title,
                 description, tag and thumbnail changes on its own.
    C  measure   7, 14 and 28 days later the video is compared with the same
                 span before the change, allowing for how the rest of the
                 back catalogue moved over those days. Each result is posted
                 on the action's issue.
    D  remember  results are pooled per situation and action, and the next
                 suggestion says what worked before.

State lives in data/actions.json. Logged actions are read from issues titled
"Action: ..." (or labelled "action") through the GitHub API, which needs
GITHUB_TOKEN and GITHUB_REPOSITORY; the workflow provides both. Without them
the logged actions already in actions.json are kept and only new detected
changes are added.
"""

import json
import os
import re
import statistics
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

from signals import SWING, ctr_change, ctr_of, z_count
from summarize import DATA_DIR, iter_shards, num, source_key

ACTIONS_PATH = os.path.join(DATA_DIR, "actions.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "snapshots.json")
HORIZONS = (7, 14, 28)
Z_RESULT = 2.0        # a result counts as better or worse at twice the normal swing
SAME_ACTION_DAYS = 3  # a detected change this close to a logged one is the same action
BACK_CATALOGUE_DAYS = 28

# key: (label, the metric the action is meant to move)
KINDS = {
    "thumbnail": ("Thumbnail / Test & Compare", "ctr"),
    "title": ("Title", "ctr"),
    "description": ("Description", "search_views"),
    "tags": ("Tags", "search_views"),
    "pinned_comment": ("Pinned comment", "views"),
    "end_screen": ("End screen / cards", "views"),
    "playlist": ("Playlist", "views"),
    "follow_up": ("Follow-up video or Short", "views"),
    "community_post": ("Community post", "views"),
    "reply_comments": ("Replied to comments", "views"),
    "external": ("Outside promotion", "views"),
    "other": ("Other", "views"),
}
# Words that identify a kind in free text, most specific first.
KIND_WORDS = [
    ("thumbnail", "thumbnail"), ("test & compare", "thumbnail"), ("title", "title"),
    ("description", "description"), ("tag", "tags"), ("pin", "pinned_comment"),
    ("end screen", "end_screen"), ("card", "end_screen"), ("playlist", "playlist"),
    ("follow-up", "follow_up"), ("follow up", "follow_up"), ("short", "follow_up"),
    ("new video", "follow_up"), ("community", "community_post"), ("repl", "reply_comments"),
    ("comment", "reply_comments"), ("promot", "external"), ("outside", "external"),
    ("reddit", "external"), ("forum", "external"),
]
METRIC_LABEL = {"ctr": "CTR", "views": "Views", "search_views": "Search views"}
METRIC_PHRASE = {"ctr": "CTR", "views": "views", "search_views": "views from YouTube search"}
# Below these, before and after together, there is nothing to measure.
ENOUGH = {"ctr": 100, "views": 10, "search_views": 10}   # impressions for CTR, else the count
SITUATIONS = ("packaging", "clicks", "wave", "losing", "conversation")
FINGERPRINTED = ("title", "description", "tags", "thumbnail")   # order in snapshots.json
VIDEO_ID = re.compile(r"(?:v=|/video/|youtu\.be/|/shorts/|^|\s)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])")


def iso(d):
    return d.strftime("%Y-%m-%d")


def span(end, days):
    return [iso(end - timedelta(days=i)) for i in range(days - 1, -1, -1)]


# ------------------------------------------------------------------ GitHub

def github(method, path, body=None):
    """A GitHub API call for this repository, or None when no token is set."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "mlmariss-youtube-analyzer"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def ensure_label():
    """The issue form tags actions with an "action" label; create it once."""
    try:
        github("GET", "/labels/action")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            try:
                github("POST", "/labels", {"name": "action", "color": "2a78d6",
                                           "description": "Something done to a video; the collector measures it"})
            except Exception as e2:
                print(f"  ! could not create the action label: {str(e2)[:120]}")
    except Exception as e:
        print(f"  ! could not check the action label: {str(e)[:120]}")


def form_fields(body):
    """Issue-form answers: {lower-case heading: text}."""
    fields, current = {}, None
    for line in (body or "").splitlines():
        if line.startswith("### "):
            current = line[4:].strip().lower()
            fields[current] = []
        elif current is not None:
            fields[current].append(line)
    out = {}
    for key, lines in fields.items():
        text = "\n".join(lines).strip()
        out[key] = "" if text == "_No response_" else text
    return out


def kind_of(text):
    low = (text or "").lower()
    for key, (label, _) in KINDS.items():
        if label.lower() in low or key.replace("_", " ") in low:
            return key
    for word, key in KIND_WORDS:
        if word in low:
            return key
    return "other" if low.strip() else None


def parse_issue(issue):
    fields = form_fields(issue.get("body"))
    title = issue.get("title") or ""
    # "Action: <what> — <video title>": only the part before the dash names the
    # action, since a video title can contain any of the keywords.
    title_kind = title.split("—")[0].split(":", 1)[-1]
    found = VIDEO_ID.search(fields.get("video", "") or "") or VIDEO_ID.search(title)
    kind = kind_of(fields.get("what did you do?") or title_kind)
    if not found or not kind:
        return None
    when = re.search(r"\d{4}-\d{2}-\d{2}", fields.get("date (if not today)", ""))
    sit = (fields.get("situation") or "").strip().lower()
    return {
        "id": f"issue-{issue['number']}", "video_id": found.group(1), "kind": kind,
        "date": when.group(0) if when else issue["created_at"][:10], "source": "logged",
        "situation": sit if sit in SITUATIONS else None,
        "issue": {"number": issue["number"], "url": issue.get("html_url"), "state": issue.get("state")},
        "notes": (fields.get("notes") or "")[:280] or None,
    }


def logged_actions():
    """Actions logged as issues, or None when GitHub cannot be read."""
    out, page = [], 1
    try:
        while True:
            batch = github("GET", f"/issues?state=all&per_page=100&page={page}")
            if batch is None:
                return None
            for issue in batch:
                if "pull_request" in issue:
                    continue
                labels = {label.get("name") for label in issue.get("labels", [])}
                if (issue.get("title") or "").lower().startswith("action:") or "action" in labels:
                    parsed = parse_issue(issue)
                    if parsed:
                        out.append(parsed)
                    else:
                        print(f"  ! issue #{issue['number']} looks like an action but names no video or action")
            if len(batch) < 100:
                return out
            page += 1
    except Exception as e:
        print(f"  ! could not read logged actions: {str(e)[:160]}")
        return None


def detected_changes():
    """Title, description, tag and thumbnail changes between daily snapshots."""
    if not os.path.exists(SNAPSHOT_PATH):
        return []
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        days = json.load(f).get("days", {})
    keys = sorted(days)
    out = []
    for i in range(1, len(keys)):
        before, after = days[keys[i - 1]].get("fingerprints"), days[keys[i]].get("fingerprints")
        if not before or not after:
            continue
        following = days[keys[i + 1]].get("fingerprints", {}) if i + 1 < len(keys) else None
        for vid, new in after.items():
            old = before.get(vid)
            if not old:
                continue
            for index, kind in enumerate(FINGERPRINTED):
                if old[index] is None or new[index] is None or old[index] == new[index]:
                    continue
                # An image can come back re-encoded once; a thumbnail change
                # counts only when the next day's snapshot still shows it.
                if kind == "thumbnail" and (not following or (following.get(vid) or [None] * 4)[3] != new[3]):
                    continue
                # Snapshots are taken early each day (UTC), so the change went
                # live during the earlier snapshot's day.
                out.append({"id": f"auto-{vid}-{kind}-{keys[i - 1]}", "video_id": vid, "kind": kind,
                            "date": keys[i - 1], "source": "detected", "situation": None,
                            "issue": None, "notes": None})
    return out


# ------------------------------------------------------------------ measuring

def load_search_views(since, through):
    """Daily views from YouTube search, per video: what description and tag changes aim at."""
    out = defaultdict(lambda: defaultdict(float))
    for day, rows in iter_shards("channel_traffic_source_a3", since, through):
        for row in rows:
            if row.get("video_id") and source_key(row) == "5":
                out[row["video_id"]][day] += num(row.get("views"))
    return out


def total(series, vid, dates, metric="views"):
    days = series.get(vid, {})
    return sum(days.get(d, {}).get(metric, 0.0) if isinstance(days.get(d), dict) else days.get(d, 0.0)
               for d in dates)


def measure(action, daily, search, published, through):
    """Fill in the 7/14/28-day results that the data now covers."""
    results = action.setdefault("results", {})
    vid, metric = action["video_id"], KINDS[action["kind"]][1]
    if vid not in daily:
        return
    day = date.fromisoformat(action["date"])
    end = date.fromisoformat(through)
    cutoff = day - timedelta(days=BACK_CATALOGUE_DAYS)
    back = [v for v, p in published.items() if p < cutoff and v != vid]
    for h in HORIZONS:
        if str(h) in results:
            continue
        if day + timedelta(days=h) > end:
            break
        before, after = span(day - timedelta(days=1), h), span(day + timedelta(days=h), h)
        imp = [total(daily, vid, before, "impressions"), total(daily, vid, after, "impressions")]
        clicks = [total(daily, vid, before, "clicks"), total(daily, vid, after, "clicks")]
        views = [total(daily, vid, before), total(daily, vid, after)]
        ctr = [ctr_of([clicks[0]], [imp[0]]), ctr_of([clicks[1]], [imp[1]])]
        tide = None
        if metric == "ctr":
            _, z = ctr_change(clicks[1], imp[1], clicks[0], imp[0])
            change = (ctr[1] / ctr[0] - 1) if ctr[0] and ctr[1] is not None else None
            volume = min(imp)
        else:
            series = search if metric == "search_views" else daily
            now, was = total(series, vid, after), total(series, vid, before)
            # How the rest of the back catalogue moved over the same days: a
            # launch or a quiet week should not be credited to (or blamed on)
            # the action.
            rest_before = sum(total(series, v, before) for v in back)
            rest_after = sum(total(series, v, after) for v in back)
            tide = rest_after / rest_before if rest_before > 0 else 1.0
            expected = was * tide
            z = z_count(now, expected, SWING["views"])
            change = (now / expected - 1) if expected else None
            volume = now + was
        results[str(h)] = {
            "before": [before[0], before[-1]], "after": [after[0], after[-1]], "metric": metric,
            "change": None if change is None else round(change * 100, 1), "z": round(z, 1),
            "verdict": ("too little data" if volume < ENOUGH[metric] else
                        "better" if z >= Z_RESULT else "worse" if z <= -Z_RESULT else "unclear"),
            "tide": None if tide is None else round(tide, 2),
            "impressions": [round(x) for x in imp], "views": [round(x) for x in views], "ctr": ctr,
            "search_views": ([round(total(search, vid, before)), round(total(search, vid, after))]
                             if metric == "search_views" else None),
        }


def result_comment(action, h, r, title):
    word = {"better": "better", "worse": "worse", "unclear": "no clear change",
            "too little data": "too little data to tell"}[r["verdict"]]
    metric = METRIC_LABEL[r["metric"]]
    rows = []
    if r["metric"] == "search_views":
        rows.append(("Search views", *r["search_views"]))
    rows += [("Impressions", *r["impressions"]), ("CTR", *[f"{x}%" if x is not None else "—" for x in r["ctr"]]),
             ("Views", *r["views"])]
    table = "\n".join(f"| {name} | {a} | {b} |" for name, a, b in rows)
    change = "" if r["change"] is None else f"{metric} {r['change']:+.1f}%"
    tide = (f" The rest of the back catalogue moved ×{r['tide']} over the same days, and the comparison "
            "allows for that." if r.get("tide") not in (None, 1.0) else "")
    return (f"<!-- yt-analyzer:result:{h} -->\n"
            f"**{h} days after: {word}**{(' (' + change + ')') if change else ''}\n\n"
            f"{KINDS[action['kind']][0]} on _{title or action['video_id']}_, "
            f"{action['date']}.\n\n"
            f"| | {r['before'][0]} – {r['before'][1]} | {r['after'][0]} – {r['after'][1]} |\n"
            f"|---|---|---|\n{table}\n\n"
            f"Measured on {METRIC_PHRASE[r['metric']]}: the change is {abs(r['z'])}× the video's normal "
            f"week-to-week swing; 2× or more counts as a real change.{tide}")


def post_results(action, title):
    """Post each new result on the action's issue, once."""
    issue = action.get("issue")
    if not issue or not os.environ.get("GITHUB_TOKEN"):
        return
    posted = action.setdefault("posted", [])
    pending = [h for h in HORIZONS if str(h) in action.get("results", {}) and str(h) not in posted]
    if not pending:
        return
    try:
        existing = github("GET", f"/issues/{issue['number']}/comments?per_page=100") or []
        bodies = " ".join(c.get("body") or "" for c in existing)
        for h in pending:
            if f"<!-- yt-analyzer:result:{h} -->" not in bodies:
                github("POST", f"/issues/{issue['number']}/comments",
                       {"body": result_comment(action, h, action["results"][str(h)], title)})
            posted.append(str(h))
    except Exception as e:
        print(f"  ! could not post results on issue #{issue['number']}: {str(e)[:160]}")


# ------------------------------------------------------------------ remembering

def build_playbook(entries):
    """Results pooled per (situation, action), plus per action in any situation."""
    groups = defaultdict(list)
    for a in entries:
        r = a.get("results", {})
        best = r.get("14") or r.get("7")
        if not best or best["verdict"] == "too little data":
            continue
        for sit in {a.get("situation") or "*", "*"}:
            groups[(sit, a["kind"])].append(best)
    out = []
    for (sit, kind), results in groups.items():
        changes = [r["change"] for r in results if r["change"] is not None]
        out.append({
            "situation": sit, "kind": kind, "label": KINDS[kind][0], "metric": METRIC_LABEL[KINDS[kind][1]],
            "tries": len(results), "better": sum(r["verdict"] == "better" for r in results),
            "unclear": sum(r["verdict"] == "unclear" for r in results),
            "worse": sum(r["verdict"] == "worse" for r in results),
            "median_change": round(statistics.median(changes), 1) if changes else None,
        })
    out.sort(key=lambda e: (e["situation"] == "*", -e["tries"]))
    return out


def annotate(steps, situation, playbook):
    """Attach what happened the previous times to each suggested step."""
    index = {(e["situation"], e["kind"]): e for e in playbook}
    for s in steps:
        e = index.get((situation, s.get("key"))) or index.get(("*", s.get("key")))
        if e:
            s["learned"] = {k: e[k] for k in ("tries", "better", "unclear", "worse", "median_change", "metric")}
            s["learned"]["scope"] = "here" if e["situation"] == situation else "anywhere"


# ------------------------------------------------------------------ main entry

def update(meta, daily, through, classify):
    """
    Sync, measure and save every action; return (actions for the dashboard,
    playbook). `classify(video_id, day)` gives the situation a video was in.
    """
    state = {"actions": []}
    if os.path.exists(ACTIONS_PATH):
        with open(ACTIONS_PATH, encoding="utf-8") as f:
            state = json.load(f)
    known = {a["id"]: a for a in state.get("actions", [])}

    if os.environ.get("GITHUB_TOKEN"):
        ensure_label()
    logged = logged_actions()
    if logged is not None:
        fresh = {a["id"] for a in logged}
        for a in logged:
            old = known.get(a["id"])
            # Keep earlier results unless the issue was edited to say something else.
            if old and all(old.get(k) == a[k] for k in ("video_id", "kind", "date")):
                a["results"], a["posted"] = old.get("results", {}), old.get("posted", [])
                a["situation"] = a["situation"] or old.get("situation")
            known[a["id"]] = a
        for key in [k for k, a in known.items() if a["source"] == "logged" and k not in fresh]:
            del known[key]   # the issue was deleted or no longer reads as an action
    for a in detected_changes():
        known.setdefault(a["id"], a)

    # A detected change next to a logged action of the same kind is that action.
    for a in [a for a in known.values() if a["source"] == "detected"]:
        for other in known.values():
            if (other["source"] == "logged" and other["video_id"] == a["video_id"] and other["kind"] == a["kind"]
                    and abs((date.fromisoformat(other["date"]) - date.fromisoformat(a["date"])).days)
                    <= SAME_ACTION_DAYS):
                other["detected"] = True
                known.pop(a["id"], None)
                break

    entries = sorted(known.values(), key=lambda a: (a["date"], a["id"]), reverse=True)
    published = {v: date.fromisoformat(m["published_at"][:10]) for v, m in meta.items() if m.get("published_at")}
    if entries:
        oldest = min(date.fromisoformat(a["date"]) for a in entries) - timedelta(days=max(HORIZONS))
        search = load_search_views(iso(oldest), through)
    for a in entries:
        if not a.get("situation"):
            a["situation"] = classify(a["video_id"], date.fromisoformat(a["date"]) - timedelta(days=1))
        measure(a, daily, search, published, through)
        post_results(a, meta.get(a["video_id"], {}).get("title"))

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = ACTIONS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"actions": entries}, f, indent=1, sort_keys=True)
    os.replace(tmp, ACTIONS_PATH)
    return entries, build_playbook(entries)
