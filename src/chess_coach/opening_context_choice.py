"""Revalidate an exact choice against the current bounded inventory."""

import re
import time

from .fact_fingerprint import canonical, digest
from .opening_unfamiliar_guard import start


def token(selection):
    return digest(canonical(selection))


def reason(report, item):
    if item["history"] == "seen_in_checked_sample":
        return "seen"
    if report["sample_failed"] or report["coverage"]["candidate_recheck_failed"]:
        return "history_unavailable"
    if item["source"] is None:
        return "source_unavailable"
    return "available"


def select(report, value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("opening selection unavailable")
    for group in report["contexts"].values():
        for parent in group["parents"]:
            for item in parent["items"]:
                if token(item["selection"]) == value and reason(report, item) == "available":
                    return item
    raise ValueError("opening selection changed")


def current(db, root, subject, binding, deadline):
    if time.monotonic() >= deadline or start(db, root, subject) != binding:
        raise ValueError("opening source changed")
