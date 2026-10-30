"""Reserve time before entering the bounded original-proof resolver."""

import time

from .style_schedule_clock import DEADLINE

PROOF_SECONDS = 5.0


def candidate_reason(item):
    if item is None:
        return "no_evidence_candidate"
    if item["status"] != "ready":
        return item["detail"]
    deadline = DEADLINE.get()
    if deadline is not None and deadline - time.monotonic() <= PROOF_SECONDS:
        return "worker_deadline"
    return None
