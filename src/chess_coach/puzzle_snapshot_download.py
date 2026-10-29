"""Stream an archive while persisting validated offsets."""

from .puzzle_snapshot_backoff import retry_at
from .puzzle_snapshot_boundary import checked_path
from .puzzle_snapshot_budget import check_budget
from .puzzle_snapshot_digest import partial_hash
from .puzzle_snapshot_http import request_headers, validate_response
from .puzzle_snapshot_state import SOURCE_URL, write_state
from .puzzle_snapshot_stream import write_response


def transfer(attempt, state, limits, deadline, client):
    archive = checked_path(attempt / "archive.zst", attempt.parents[2])
    offset = archive.stat().st_size if archive.exists() else 0
    if offset != state.get("downloaded_bytes", 0):
        raise ValueError("partial archive differs from checkpoint")
    digest = partial_hash(archive, offset, state, limits, deadline)
    with client.stream("GET", SOURCE_URL, headers=request_headers(state, offset)) as response:
        if response.status_code in (429, 503):
            state["retry_after"] = response.headers.get("retry-after", "")[:128]
            state["retry_at"] = retry_at(state["retry_after"])
            raise ValueError("provider requested backoff")
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ValueError("unexpected content encoding")
        validate_response(response, state, offset)
        check_budget(attempt, limits, deadline, state["expected_bytes"], limits.max_archive_bytes)
        state["phase"] = "downloading"
        write_state(attempt, state)
        write_response(response, archive, attempt, state, limits, deadline, digest)
    if state["downloaded_bytes"] != state["expected_bytes"]:
        raise ValueError("truncated archive response")
    state["archive_complete"] = True
    state["phase"] = "downloaded"
    write_state(attempt, state)
    return archive
