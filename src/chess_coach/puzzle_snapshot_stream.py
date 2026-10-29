"""Checkpoint archive bytes only after durable writes."""

import os
import time

from .puzzle_snapshot_budget import check_budget
from .puzzle_snapshot_state import write_state


def write_response(response, archive, attempt, state, limits, deadline, digest):
    with archive.open("ab" if archive.exists() else "xb") as out:
        for chunk in response.iter_raw():
            size = state["downloaded_bytes"] + len(chunk)
            check_budget(attempt, limits, deadline, size, state["expected_bytes"], len(chunk))
            if size > limits.max_archive_bytes:
                raise ValueError("archive byte limit exceeded")
            out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
            digest.update(chunk)
            state["partial_sha256"] = digest.hexdigest()
            state["downloaded_bytes"] = size
            write_state(attempt, state)
    if time.monotonic() >= deadline:
        raise TimeoutError("snapshot time limit reached")
