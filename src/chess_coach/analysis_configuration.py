"""Record the analysis limits and decision/score conventions."""


def engine_config(binary, nodes, time_limit, depth, multipv, threads, hash_mb, compatibility):
    config = {
        "nodes": nodes,
        "depth": depth,
        "multipv": multipv,
        "threads": threads,
        "hash_mb": hash_mb,
        "engine_path": str(binary),
        "compatibility": compatibility,
        "position_semantics": "pre_move_v1",
        "score_perspective": "side_to_move",
        "mate_score": 100000,
    }
    if time_limit is not None:
        config["time_limit"] = time_limit
    return config
