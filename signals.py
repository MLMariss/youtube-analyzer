"""
Week-on-week change tests, shared by monitor.py (finding changes) and
actions.py (measuring whether an action helped).

Every comparison is a video against itself. A count (impressions, views)
changes "clearly" when the gap is several times what that video's numbers
normally do from one week to the next; CTR is tested as a ratio.
"""

import math
import statistics

# How much one video's numbers normally move from one week to the next,
# measured on this channel's archive (the robust spread of week-on-week
# changes for videos with 150+ a week): impressions about ±17%, views ±27%,
# CTR ±9%. Comments and dislikes are too sparse to measure; they use the
# views figure.
SWING = {"impressions": 0.17, "views": 0.27, "comments": 0.27, "dislikes": 0.27}
CTR_SWING = 0.09

Z_CLEAR = 3.0         # a change must be about three times the normal swing
Z_TRIM = 2.0          # ...and still twice it with the week's biggest day removed
Z_STEP = 1.0          # in a two-week climb the latest week must still be going up


def z_count(now, before, swing):
    """
    How many "normal swings" separate this week's count from last week's.

    The expected spread is counting noise (now + before, as for any count)
    plus the video's normal week-to-week variation (swing × each count). Small
    counts are dominated by the first, large ones by the second, so 0 -> 3
    and 10,000 -> 11,000 are both correctly ordinary.
    """
    var = now + before + swing * swing * (now * now + before * before)
    return 0.0 if var <= 0 else (now - before) / math.sqrt(var)


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


def building_up(days14, swing):
    """Up three days running and clearly above last week's pace, before a full week confirms it."""
    last, this = days14[:7], days14[7:]
    pace = sum(last) / 7
    n3, e3 = sum(this[-3:]), 3 * pace
    var = n3 + e3 * 3 / 7 + swing * swing * (n3 * n3 + e3 * e3)
    z3 = 0.0 if var <= 0 else (n3 - e3) / math.sqrt(var)
    return z3 >= Z_CLEAR and min(this[-3:]) > pace


def ctr_change(clicks_now, imp_now, clicks_before, imp_before):
    """(direction, z) for CTR this week against last week."""
    if imp_now < 1 or imp_before < 1:
        return 0, 0.0
    cn, cb = clicks_now + 0.5, clicks_before + 0.5
    ratio = math.log((cn / imp_now) / (cb / imp_before))
    var = max(1 / cn - 1 / imp_now, 0) + max(1 / cb - 1 / imp_before, 0) + 2 * CTR_SWING ** 2
    z = ratio / math.sqrt(var)
    return (1 if z >= Z_CLEAR else -1 if z <= -Z_CLEAR else 0), z


def ctr_of(clicks, impressions):
    total = sum(impressions)
    return round(sum(clicks) / total * 100, 2) if total else None


