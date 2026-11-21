"""Bound the per-run records considered by the capacity inventory."""

from .analysis_history_identity import Limit, bytesize, profile
from .analysis_history_inventory_record import records

MAX_SCAN_BYTES = 128 * 1024 * 1024


def row(state, values, *, engine_index):
    (
        run_id,
        game_id,
        engine,
        version,
        path,
        binary,
        created,
        raw_config,
        raw_nnue,
        raw_compatibility,
        linked,
        config,
        nnue,
        compatibility,
    ) = values
    if type(run_id) is not int or type(game_id) is not int:
        raise Limit("unsupported run identity")
    metadata = [bytesize(value) for value in (engine, version, path, binary, created)]
    raw_bytes = sum(bytesize(value) for value in (raw_config, raw_nnue, raw_compatibility))
    key, profile_bytes = profile(state, (config, nnue, compatibility))
    scanned = sum(metadata) + raw_bytes + (profile_bytes if linked else 0)
    state["scanned_bytes"] += scanned
    if state["scanned_bytes"] > MAX_SCAN_BYTES:
        raise Limit("inventory byte limit")
    records(state, metadata, raw_bytes, linked, engine_index)
    return key
