"""Inventory all analysis profile identities without exposing their contents."""

import sqlite3
import time

from .analysis_history_identity import (
    MAX_DISTINCT,
    MAX_DISTINCT_BYTES,
    MAX_PROFILE_BYTES,
    Limit,
)
from .analysis_history_inventory_record import MAX_INDEX_BYTES
from .analysis_history_inventory_scan import MAX_ROWS, SAMPLE_LIMIT, scan
from .analysis_history_inventory_state import MAX_SCAN_BYTES

SCAN_SECONDS = 60


def _state():
    return {
        "identities": {},
        "identity_bytes": 0,
        "profile_encoded_bytes": 0,
        "profile_text_bytes": 0,
        "profile_overflow_pages": 0,
        "scanned_bytes": 0,
        "run_overflow_pages": 0,
        "original_run_overflow_pages": 0,
        "run_record_bytes": 0,
        "engine_index_record_bytes": 0,
        "engine_index_overflow_pages": 0,
    }


def inventory(connection, deadline, *, native, engine_index):
    """Return complete aggregates, or an explicitly incomplete result."""
    state = _state()
    until = min(time.monotonic() + SCAN_SECONDS, deadline.end - 10)
    connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        count, distinct, sample = scan(connection, state, until, native, engine_index)
    except (Limit, sqlite3.Error, ValueError, UnicodeError):
        return {"inventory_complete": False, "inventory_limits": limits()}
    finally:
        connection.set_progress_handler(deadline.progress, 1000)
    result = {key: value for key, value in state.items() if key != "identities"}
    result.update(
        {
            "inventory_complete": True,
            "inventory_limits": limits(),
            "inventory_rows": count,
            "distinct_profiles": distinct,
            "distinct_stored_profiles": len(state["identities"]),
            "sampled_rows": min(count, SAMPLE_LIMIT),
            "distinct_sampled_profiles": sample,
            "repeated_sampled_rows": min(count, SAMPLE_LIMIT) - sample,
            "sample_complete": count <= SAMPLE_LIMIT,
        }
    )
    return result


def limits():
    return {
        "rows": MAX_ROWS,
        "scan_bytes": MAX_SCAN_BYTES,
        "profile_bytes": MAX_PROFILE_BYTES,
        "distinct_profiles": MAX_DISTINCT,
        "distinct_memory_bytes": MAX_DISTINCT_BYTES,
        "index_input_bytes": MAX_INDEX_BYTES,
        "seconds": SCAN_SECONDS,
    }
