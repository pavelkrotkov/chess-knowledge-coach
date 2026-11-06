"""Record the analysis limits and decision/score conventions."""

from .engine_report_cache import engine_digest


def engine_config(binary, nodes, time_limit, depth, multipv, threads, hash_mb, compatibility):
    binary_sha256 = engine_digest(binary)
    config = {
        "nodes": nodes,
        "depth": depth,
        "multipv": multipv,
        "played_multipv": 1,
        "threads": threads,
        "hash_mb": hash_mb,
        "engine_path": str(binary),
        "engine_sha256": binary_sha256,
        "compatibility": compatibility,
        "position_semantics": "pre_move_v1",
        "comparison_semantics": "same-board-roots-v1",
        "limits_apply_per_search": True,
        "score_perspective": "side_to_move",
        "mate_score": 100000,
    }
    if time_limit is not None:
        config["time_limit"] = time_limit
    return config
