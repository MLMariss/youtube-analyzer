"""
Change tests, shared by monitor.py (finding changes) and actions.py
(measuring whether an action helped).

Every comparison is a video against itself, as a ratio: a count changes
"clearly" when it moved several times what that video's numbers normally do
from one week to the next, once plain counting noise is allowed for. CTR is
tested the same way.

Two kinds of change:

    this week   jump / drop / climb / slide: this week against last week (or
                the week before), for news that is happening now
    shift       the level moved on some date and has not gone back: a game
                update in September still bringing three times the summer
                views in October, long after "this week" stopped seeing it
"""

import math
import statistics

# How much one video's numbers normally move from one week to the next,
# measured on this channel's archive: the swing that gives the week-on-week
# changes of videos with 30+ a week a robust spread of one, after counting
# noise. Impressions ±23%, views ±27%, CTR ±8%. Comments and dislikes are too
# sparse to measure; they use the views figure.
SWING = {"impressions": 0.23, "views": 0.27, "comments": 0.27, "dislikes": 0.27}
CTR_SWING = 0.08

Z_CLEAR = 2.0         # a change must be twice the normal swing: about the top 5% of weeks
Z_TRIM = 1.5          # ...and still 1.5 times it with the week's biggest day removed
Z_STEP = 1.0          # in a two-week climb the latest week must still be going up

# Over months a video's level wanders further than from one week to the next,
# and trying every date as the split finds a fair-sized gap by chance alone,
# so a shift needs a wider swing and a higher bar. Calibrated on the archive:
# about the top 5% of splits, roughly three times the old level for a busy
# video and more for a quiet one, where counting noise adds to the swing.
SHIFT_SWING = 0.30
Z_SHIFT = 3.5
Z_STILL = 2.0         # ...and last week must still be clearly away from the old level
SHIFT_BEFORE = 84     # days of the old level the new one is compared with
SHIFT_MIN_BEFORE = 28
SHIFT_MIN_AFTER = 14  # anything newer is this week's tests' job
SHIFT_TREND = 0.15    # last week this far above or below the average since: still moving


def rate_z(now, now_days, before, before_days, swing):
    """
    How many normal swings separate two totals, as rates per day.

    On a log scale the spread allowed for is the normal swing plus counting
    noise (1/count), so 0 -> 3 is ordinary at any swing and 1,000 -> 1,600 a
    week is not. The +0.5 keeps empty periods finite.
    """
    ratio = math.log(((now + 0.5) / now_days) / ((before + 0.5) / before_days))
    return ratio / math.sqrt(swing * swing + 1 / (now + 0.5) + 1 / (before + 0.5))


def z_count(now, before, swing):
    """rate_z for two totals over periods of the same length."""
    return rate_z(now, 1, before, 1, swing)


def without_spike(days):
    """A week's total with its biggest single day replaced by the week's median day."""
    return sum(days) - max(days) + statistics.median(days)


def weekly_change(days21, swing):
    """
    (direction, how, z) for 21 daily values, oldest first: the week before
    last, last week and this week.

    jump / drop    this week clearly differs from last week, still does with
                   the spike day removed, and the last three days agree
    climb / slide  two weeks in a row the same way, clearly different from two
                   weeks ago, and the latest week still moving that way
    """
    before2, last, this = days21[:7], days21[7:14], days21[14:]
    w2, w1, w0 = sum(before2), sum(last), sum(this)
    recent, usual = sum(this[-3:]) / 3, w1 / 7
    z = z_count(w0, w1, swing)
    if z >= Z_CLEAR and z_count(without_spike(this), w1, swing) >= Z_TRIM and recent > usual:
        return 1, "jump", z
    if z <= -Z_CLEAR and z_count(w0, without_spike(last), swing) <= -Z_TRIM and recent < usual:
        return -1, "drop", z
    z2 = z_count(w0, w2, swing)
    if (w0 > w1 > w2 and z2 >= Z_CLEAR and z >= Z_STEP
            and z_count(without_spike(this), w2, swing) >= Z_TRIM and recent >= usual):
        return 1, "climb", z2
    if (w0 < w1 < w2 and z2 <= -Z_CLEAR and z <= -Z_STEP
            and z_count(w0, without_spike(before2), swing) <= -Z_TRIM and recent <= usual):
        return -1, "slide", z2
    return 0, None, z


def best_split(cum, first, swing):
    """(z, split, start of the level before) for the split of cum[first:] that stands out most."""
    n = len(cum) - 1
    best = None
    for t in range(first + SHIFT_MIN_BEFORE, n - SHIFT_MIN_AFTER + 1):
        lo = max(first, t - SHIFT_BEFORE)
        z = rate_z(cum[n] - cum[t], n - t, cum[t] - cum[lo], t - lo, swing)
        if best is None or abs(z) > abs(best[0]):
            best = (z, t, lo)
    return best


def shift(days, swing=SHIFT_SWING):
    """
    The date a level last moved and stayed moved, or None.

    `days` is (date, value) pairs, oldest first, for the days that have data.
    Every date with four weeks before it and two after is tried as the split:
    the average since then against the twelve weeks before. The split that
    stands out most is a shift if it clears Z_SHIFT; the days after it are then
    searched again, against the level since, so a game that rose in June and
    again in September reports September. A step back only replaces a rise once
    the rise no longer holds: a wave easing off is still the wave. The shift
    counts if last week is still clearly away from the level before it (a
    burst that passed is no shift).

    Returns the date, the weekly level before, since and last week, the
    biggest (or, for a fall, smallest) week since, and `trend`: whether last
    week was above (1), below (-1) or near (0) the average since.
    """
    n = len(days)
    cum = [0.0]
    for _, v in days:
        cum.append(cum[-1] + v)
    chain, first = [], 0
    while True:
        best = best_split(cum, first, swing)
        if not best or abs(best[0]) < Z_SHIFT:
            break
        chain.append(best)
        first = best[1]
    if not chain:
        return None
    now = cum[n] - cum[n - 7]
    holds = lambda split: rate_z(now, 7, cum[split[1]] - cum[split[2]], split[1] - split[2], swing) \
        * (1 if split[0] > 0 else -1)
    found = chain[0]
    for later in chain[1:]:
        if later[0] * found[0] > 0 or holds(found) < Z_STILL:
            found = later
    z, t, lo = found
    before = cum[t] - cum[lo]
    z_now = rate_z(now, 7, before, t - lo, swing)
    if z_now * z < 0 or abs(z_now) < Z_STILL:
        return None
    direction = 1 if z > 0 else -1
    since = (cum[n] - cum[t]) / (n - t) * 7
    peak = max(range(t, n - 6), key=lambda i: (cum[i + 7] - cum[i]) * direction)
    trend = 1 if now > since * (1 + SHIFT_TREND) else -1 if now < since * (1 - SHIFT_TREND) else 0
    return {"dir": direction, "date": days[t][0], "z": round(z, 1), "z_now": round(z_now, 1),
            "before": round(before / (t - lo) * 7), "since": round(since), "now": round(now),
            "peak": round(cum[peak + 7] - cum[peak]), "peak_from": days[peak][0], "trend": trend}


def building_up(days14, swing):
    """Up three days running and clearly above last week's pace, before a full week confirms it."""
    last, this = days14[:7], days14[7:]
    pace = sum(last) / 7
    return rate_z(sum(this[-3:]), 3, sum(last), 7, swing) >= Z_CLEAR and min(this[-3:]) > pace


def ctr_change(clicks_now, imp_now, clicks_before, imp_before):
    """(direction, z) for CTR this week against last week."""
    if imp_now < 1 or imp_before < 1:
        return 0, 0.0
    cn, cb = clicks_now + 0.5, clicks_before + 0.5
    ratio = math.log((cn / imp_now) / (cb / imp_before))
    var = max(1 / cn - 1 / imp_now, 0) + max(1 / cb - 1 / imp_before, 0) + CTR_SWING ** 2
    z = ratio / math.sqrt(var)
    return (1 if z >= Z_CLEAR else -1 if z <= -Z_CLEAR else 0), z


def ctr_of(clicks, impressions):
    total = sum(impressions)
    return round(sum(clicks) / total * 100, 2) if total else None
