"""Summarize bounded public check responses without learner inference."""

import time
from collections import Counter

from .fact_fingerprint import canonical, digest
from .opening_check_response_counts import record, totals
from .opening_check_response_replay import replay

VERSION = "public-check-response-v1"


def summarize(db, rows, decision, move, control, deadline):
    if control == "unknown":
        return {"version": VERSION, "status": "unavailable", "reason": "nominal_context_unknown"}
    counts, example = Counter(), None
    for game_id, total, context in rows:
        if time.monotonic() >= deadline:
            break
        try:
            item = replay(db, game_id, total, decision, move, deadline)
        except TimeoutError:
            break
        counts[item["status"]] += 1
        counts["checked_games"] += int(bool(item["events"]))
        counts["unanswered"] += int(item["unanswered"])
        for observation in item["events"]:
            record(counts, observation)
            if example is None:
                example = {
                    **observation,
                    "record": game_id,
                    "record_sha256": digest(canonical([game_id, context])),
                }
    return {"version": VERSION, **totals(counts, len(rows), example)}
