#!/usr/bin/env python3
"""
Google Trends for discover.py, through SerpApi's free tier.

SerpApi's Google Trends engine returns what trends.google.com shows: related
queries (top and rising) and interest over time, for Google web search,
worldwide unless a country is given. Each call is one search.

Interest over time compares up to five terms on one scale: 100 is the
busiest day of the busiest term, every other value is a share of it. That
shared scale is what discover.py sizes questions with.

The free plan gives 250 searches a cycle, renewing on the 12th, at up to 250 an
hour. Automation spends at most CAP of them per cycle and leaves the rest for
manual checks. Before spending, the searches left are read from SerpApi's
account endpoint, which is free; the ledger in data/discover.json (kept by
discover.py) is the fallback when that endpoint cannot be read.

The API key travels in the query string, so every message that could carry a
URL goes through redact() before it is printed, and nothing SerpApi returns is
stored except the lists asked for (its account endpoint also returns the key
and the account email).

Later the official Google Trends API (alpha) can replace SerpApi here:
discover.py only calls related_queries(), interest_over_time() and Budget.

Usage (manual checks, from the 50 searches automation leaves alone):
    SERPAPI_KEY=... python trends.py account
    SERPAPI_KEY=... python trends.py queries "tropico 6"
    SERPAPI_KEY=... python trends.py compare "snowrunner" "snowrunner mods"
"""

import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

SEARCH_URL = "https://serpapi.com/search.json"
ACCOUNT_URL = "https://serpapi.com/account.json"
CAP = 200            # searches automation may spend per cycle; the other 50 are yours
CYCLE_DAY = 12       # the free plan renews on the 12th of each month
GAMES_CAT = 8        # Google Trends category "Games": keeps "Foundation" the game, not the make-up
TIMEOUT = 60         # SerpApi waits for Google; a Trends search can take a while
USER_AGENT = "mlmariss-youtube-analyzer"
NO_RESULTS = re.compile(r"hasn'?t returned any results|no results", re.I)
MAX_TERMS = 5        # Google Trends compares at most five terms at once
LESS_THAN_ONE = 0.5  # how a "<1" day is counted: some searches, under one point


class TrendsError(RuntimeError):
    pass


def api_key():
    return (os.environ.get("SERPAPI_KEY") or "").strip()


def redact(text):
    """`text` with the API key, and any api_key= value, blanked out."""
    text = str(text)
    key = api_key()
    if key:
        text = text.replace(key, "***")
    return re.sub(r"(api_key=)[^&\s\"']+", r"\1***", text)


def cycle_start(today):
    """The date the current SerpApi cycle began: the most recent 12th."""
    if today.day >= CYCLE_DAY:
        return today.replace(day=CYCLE_DAY)
    prev = today.replace(day=1) - timedelta(days=1)
    return prev.replace(day=min(CYCLE_DAY, prev.day))


def next_cycle(start):
    """The day the cycle that began on `start` ends: the 12th of the next month."""
    return (start.replace(day=1) + timedelta(days=32)).replace(day=CYCLE_DAY)


def get(url, params):
    query = urllib.parse.urlencode({**params, "api_key": api_key()})
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {}
        raise TrendsError(redact(f"HTTP {e.code}: {body.get('error') or e.reason}")) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, json.JSONDecodeError) as e:
        raise TrendsError(redact(f"{type(e).__name__}: {e}")) from None


def account():
    """Searches left this cycle, by SerpApi's own count (a free call): {"left", "per_cycle", "used"}."""
    try:
        data = get(ACCOUNT_URL, {})
    except TrendsError as e:
        if not str(e).startswith("HTTP 404"):
            raise
        data = get(ACCOUNT_URL.replace(".json", ""), {})
    if data.get("error"):
        raise TrendsError(redact(data["error"]))

    def n(k):
        v = data.get(k)
        return int(v) if isinstance(v, (int, float)) else None

    left = n("total_searches_left")
    if left is None:
        left = n("plan_searches_left")
    return {"left": left, "per_cycle": n("searches_per_month"), "used": n("this_month_usage")}


class Budget:
    """
    How many searches automation may still spend this cycle.

    `ledger` is the dict discover.py keeps in data/discover.json:
    {"cycle": "YYYY-MM-DD", "used": n, "log": [...]}. It starts over when a new
    cycle begins. The account endpoint, when it answers, is the truth for what
    is left on the plan; the ledger caps what automation itself has spent.
    """

    def __init__(self, ledger, today=None, cap=CAP):
        today = today or datetime.now(timezone.utc).date()
        start = cycle_start(today).isoformat()
        if ledger.get("cycle") != start:
            ledger.clear()
            ledger.update({"cycle": start, "used": 0, "log": []})
        self.ledger, self.cap, self.today = ledger, cap, today
        self.account = None

    def check_account(self):
        try:
            self.account = account()
        except TrendsError as e:
            print(f"  ! could not read SerpApi's searches left: {e}")
        return self.account

    def left(self):
        mine = self.cap - self.ledger.get("used", 0)
        plan = (self.account or {}).get("left")
        return max(0, mine if plan is None else min(mine, plan))

    def spend(self, what):
        self.ledger["used"] = self.ledger.get("used", 0) + 1
        self.ledger.setdefault("log", []).append({"date": self.today.isoformat(), "what": what})
        self.ledger["log"] = self.ledger["log"][-60:]
        if self.account and isinstance(self.account.get("left"), int):
            self.account["left"] -= 1


def parse_rise(item):
    """(rise in %, breakout?) for a rising entry: "+250%" -> (250, False), "Breakout" -> (None, True)."""
    value = str(item.get("value") or "")
    if "breakout" in value.lower():
        return None, True
    digits = re.sub(r"[^\d]", "", value)
    if digits:
        return int(digits), False
    ev = item.get("extracted_value")
    return (int(ev), False) if isinstance(ev, (int, float)) else (None, False)


def related_queries(term, date_range="today 3-m", cat=None, geo=None, budget=None):
    """
    Google's related queries for `term` on web search:
    {"rising": [{"query", "rise", "breakout"}], "top": [{"query", "score"}]}.
    Empty lists when Google has too little data for the term.
    """
    if not api_key():
        raise TrendsError("SERPAPI_KEY is not set")
    if budget is not None and budget.left() <= 0:
        raise TrendsError("the search budget for this cycle is spent")
    params = {"engine": "google_trends", "data_type": "RELATED_QUERIES", "q": term, "date": date_range}
    if cat:
        params["cat"] = str(cat)
    if geo:
        params["geo"] = geo
    started = time.monotonic()
    try:
        data = get(SEARCH_URL, params)
    finally:
        if budget is not None:
            budget.spend(f"related queries: {term}")
    err = data.get("error")
    if err and not NO_RESULTS.search(err):
        raise TrendsError(redact(err))
    rq = data.get("related_queries") or {}
    rising, top = [], []
    for item in rq.get("rising") or []:
        q = str(item.get("query") or "").strip()
        if q:
            rise, breakout = parse_rise(item)
            rising.append({"query": q, "rise": rise, "breakout": breakout})
    for item in rq.get("top") or []:
        q = str(item.get("query") or "").strip()
        ev = item.get("extracted_value")
        if q:
            top.append({"query": q, "score": int(ev) if isinstance(ev, (int, float)) else None})
    print(f"  · {term}: {len(rising)} rising, {len(top)} top ({time.monotonic() - started:.1f}s)")
    return {"rising": rising, "top": top}


def point(item):
    """One day's value: 45 for "45", LESS_THAN_ONE for "<1", 0 for nothing."""
    ev = item.get("extracted_value")
    raw = str(item.get("value") or "").strip()
    if raw.startswith("<"):
        return LESS_THAN_ONE
    if isinstance(ev, (int, float)):
        return float(ev)
    digits = re.sub(r"[^\d.]", "", str(ev if ev is not None else raw))
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def interest_over_time(terms, date_range="today 3-m", cat=None, geo=None, budget=None):
    """
    Up to five terms on one shared scale over `date_range`:
    {"dates": [...], "series": {term: [values]}}, values 0-100 where 100 is
    the busiest day of the busiest term. A term Google has too little data on
    is all zeros. Commas are taken out of terms (they separate them).
    """
    if not api_key():
        raise TrendsError("SERPAPI_KEY is not set")
    if budget is not None and budget.left() <= 0:
        raise TrendsError("the search budget for this cycle is spent")
    terms = [re.sub(r"\s+", " ", t.replace(",", " ")).strip() for t in terms][:MAX_TERMS]
    params = {"engine": "google_trends", "data_type": "TIMESERIES", "q": ",".join(terms), "date": date_range}
    if cat:
        params["cat"] = str(cat)
    if geo:
        params["geo"] = geo
    started = time.monotonic()
    try:
        data = get(SEARCH_URL, params)
    finally:
        if budget is not None:
            budget.spend(f"interest over time: {', '.join(terms)}")
    err = data.get("error")
    if err and not NO_RESULTS.search(err):
        raise TrendsError(redact(err))
    timeline = (data.get("interest_over_time") or {}).get("timeline_data") or []
    dates, series = [], {t: [] for t in terms}
    for row in timeline:
        values = row.get("values") or []
        by_name = {str(v.get("query") or "").strip().lower(): v for v in values}
        dates.append(str(row.get("date") or row.get("timestamp") or ""))
        for i, t in enumerate(terms):
            # Google echoes each term back; fall back to its position.
            v = by_name.get(t.lower()) or (values[i] if i < len(values) else {})
            series[t].append(point(v))
    print(f"  · compared {len(terms)} terms over {len(dates)} days ({time.monotonic() - started:.1f}s)")
    return {"dates": dates, "series": series}


def main(argv):
    if len(argv) < 2 or argv[1] not in ("account", "queries", "compare"):
        print('Usage:\n  python trends.py account\n  python trends.py queries "tropico 6"\n'
              '  python trends.py compare "snowrunner" "snowrunner mods"')
        return 2
    if not api_key():
        print("Set SERPAPI_KEY first.")
        return 2
    try:
        if argv[1] == "account":
            print(json.dumps(account(), indent=2))
        elif argv[1] == "compare":
            terms = [t for t in argv[2:] if t.strip()]
            if not terms:
                print('Usage: python trends.py compare "snowrunner" "snowrunner mods"')
                return 2
            got = interest_over_time(terms)
            for t, vals in got["series"].items():
                avg = sum(vals) / len(vals) if vals else 0
                print(f"  {t:40s} average {avg:5.1f}  peak {max(vals or [0]):5.1f}")
        else:
            term = " ".join(argv[2:]).strip()
            if not term:
                print('Usage: python trends.py queries "tropico 6"')
                return 2
            print(json.dumps(related_queries(term), indent=2, ensure_ascii=False))
    except TrendsError as e:
        print(f"Failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
