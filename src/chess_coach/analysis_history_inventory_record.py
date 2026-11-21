"""Accumulate upper bounds for analysis table and optional index records."""

from .analysis_history_identity import Limit
from .analysis_history_pages import overflow

MAX_INDEX_BYTES = 32 * 1024 * 1024


def records(state, metadata, raw_bytes, linked, engine_index):
    # Already-linked rows are copied unchanged, including any inline values.
    compact_payload = 256 + sum(metadata) + (raw_bytes if linked else 0)
    state["run_overflow_pages"] += overflow(compact_payload)
    state["original_run_overflow_pages"] += overflow(256 + sum(metadata) + raw_bytes)
    state["run_record_bytes"] += compact_payload
    if engine_index:
        _index(state, metadata[0])


def _index(state, engine_bytes):
    payload = 128 + engine_bytes
    state["engine_index_record_bytes"] += payload
    if state["engine_index_record_bytes"] > MAX_INDEX_BYTES:
        raise Limit("index input limit")
    state["engine_index_overflow_pages"] += overflow(payload, index=True)
