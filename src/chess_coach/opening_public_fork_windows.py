"""Bound the existing initial and continuation public-history windows."""

from .opening_profile_play import STORED_PLIES

WINDOW = 36


def bounds(ply, total, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid fork window")
    first = ply + (WINDOW if window == "continuation" else 0)
    frontier = STORED_PLIES if window == "initial" else total
    return first, min(first + WINDOW - 1, total, frontier)
