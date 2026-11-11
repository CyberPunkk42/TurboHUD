"""The blue and yellow flags in one spot (asked for by the user on 2026-11-11). A player may
place both in the same spot. Stacked one next to the other, they covered twice as much of the
track (seen by the user), so where both are out and their boxes overlap they are combined
instead: the yellow box, where and as large as it is, with a blue frame (the blue flag's colour
and fade), and no separate blue bar. Placed apart, each shows in its own spot. Nothing is ever
moved. Places are (x, y, width, height) in screen pixels.
"""

FLAG_SECTIONS = ('yellowflag', 'blueflag')


def overlap(a, b):
    """Whether boxes `a` and `b` share any area."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def combined(yellow_place, blue_place, yellow_out, blue_out):
    """Whether to show the blue flag as a frame on the yellow box: both out, overlapping."""
    return bool(yellow_out and blue_out) and overlap(yellow_place, blue_place)
