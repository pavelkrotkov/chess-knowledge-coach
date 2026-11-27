"""Bind the public named-piece protection objective and its existing limits."""

import chess

from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES
from .objective_protection_before import MAX_CAPTURES
from .objective_protection_judge import VERSION as VERIFIER
from .opening_public_proof_versions import current as current_preparation

VERSION = "public-opening-piece-protection-v1"


def protection(identity, *, forks=False, prevent=False, window="initial"):
    if forks or prevent or window != "initial":
        raise ValueError("invalid protection selection")
    policy = {
        **identity["policy"],
        "protection": {
            "objective": "protect_threatened_piece",
            "verifier": VERIFIER,
            "chess_version": chess.__version__,
            "minimum_gain": 3,
            "capture_limit": MAX_CAPTURES,
            "reply_limit": MAX_REPLIES,
            "exchange_nodes": MAX_EXCHANGE_NODES,
            "exchange_plies": MAX_EXCHANGE_PLIES,
            "recorded_moves_only": True,
        },
    }
    return {**identity, "version": VERSION, "policy": policy}


def selected(directory, identity, window):
    chosen = protection(identity, window=window)
    return (*current_preparation(directory, identity, chosen=chosen), None)
