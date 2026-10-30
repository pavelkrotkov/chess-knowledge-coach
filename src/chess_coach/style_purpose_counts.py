"""Explicit slot coverage categories for each deterministic allocation."""

from collections import Counter

KINDS = ("target", "control")
STATES = (
    "slots",
    "pending",
    "running",
    "interrupted",
    "insufficient",
    "unknown",
    "source_unknown",
    "context_unknown",
    "outside_sample",
    "stale",
    "duplicate",
    "outside_check",
    "forced_move",
    "comparable",
)


def coverage_counts():
    return Counter({f"{kind}_{state}": 0 for kind in KINDS for state in STATES})
