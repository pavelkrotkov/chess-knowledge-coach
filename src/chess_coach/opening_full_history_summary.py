"""Summarize selected independent public games and their later windows."""

import time
from collections import Counter

from .opening_full_history_attempt import attempt

VERSION = "public-full-history-tail-v1"


def summarize(db, rows, decision, branch, deadline):
    counts, example = Counter(), None
    for row in rows:
        if time.monotonic() >= deadline:
            break
        try:
            result = attempt(db, row, decision, branch, deadline)
        except TimeoutError:
            break
        if result is None:
            counts["unsupported"] += 1
            continue
        counts["analyzed"] += 1
        counts["ended_before_later"] += int(result["example"] is None)
        counts["censored"] += int(result["censored"])
        counts["board_terminal"] += int(result["board_terminal"])
        if example is None and result["example"] is not None:
            example = result
    incomplete = len(rows) - counts["analyzed"] - counts["unsupported"]
    return {
        "version": VERSION,
        "status": "incomplete" if incomplete else "complete",
        "selected": len(rows),
        "analyzed": counts["analyzed"],
        "unsupported": counts["unsupported"],
        "ended_before_later": counts["ended_before_later"],
        "censored": counts["censored"],
        "board_terminal": counts["board_terminal"],
        "incomplete": incomplete,
        "interrupted": bool(incomplete),
        "example": example,
    }
