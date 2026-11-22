"""Bind the separate public knight-fork prevention execution policy."""

import chess

from .fork_defense_anchor import MAX_ANCHOR_MOVES, MAX_PROOFS
from .fork_defense_probe import MAX_CANDIDATES as PROBE_CANDIDATES
from .fork_defense_scan import MAX_CANDIDATES as SCAN_CANDIDATES
from .fork_proof import MAX_REPLIES
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .objective_fork_defense_budget import ANSWER_UNITS, LIMIT
from .opening_full_history_build import TRANSFORM


def prevention(identity, sha, window):
    policy = {
        **identity["policy"],
        "prevention": {
            "version": "public-knight-fork-prevention-v1",
            "window": window,
            "positions": 36,
            "stored_frontier": 52,
            "index_sha256": sha,
            "transform": TRANSFORM,
            "chess_version": chess.__version__,
            "proofs_per_preparation": 32,
            "alternatives_per_position": 8,
            "stop_after_first_example_per_game": True,
            "games_per_branch": 10,
            "anchor_moves": MAX_ANCHOR_MOVES,
            "anchor_proofs": MAX_PROOFS,
            "probe_candidates": PROBE_CANDIDATES,
            "scan_candidates": SCAN_CANDIDATES,
            "owned_scope_units": LIMIT,
            "owned_answer_reservation": ANSWER_UNITS,
            "minimum_gain": 3,
            "reply_limit": MAX_REPLIES,
            "exchange_nodes": MAX_EXCHANGE_NODES,
            "exchange_plies": MAX_EXCHANGE_PLIES,
        },
    }
    return {**identity, "version": "public-opening-fork-prevention-v1", "policy": policy}
