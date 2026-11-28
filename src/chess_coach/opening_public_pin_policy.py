"""Bind the existing pin verifier to one exact indexed public window."""

import chess

from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .objective_pin_contract import GOAL, OBJECTIVE, VERIFIER
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES
from .pin_pipeline import VERSION as PIN_VERSION
from .pin_proof import MAX_REPLIES

VERSION = "public-opening-pin-execution-v1"
ROOTS_PER_GAME = 64
PROOFS_PER_BRANCH = 8


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid pin window")
    pin = {
        "version": VERSION,
        "producer": "pin-execute",
        "mapper": "pin-execute-mapper",
        "pin_version": PIN_VERSION,
        "operation": "execute",
        "scope": "pin-execute-v1",
        "objective": OBJECTIVE,
        "goal": GOAL,
        "verifier": VERIFIER,
        "window": window,
        "positions": WINDOW,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
        "games_per_branch": MAX_GAMES,
        "roots_per_game": ROOTS_PER_GAME,
        "proofs_per_branch": PROOFS_PER_BRANCH,
        "proofs_per_preparation": 2 * PROOFS_PER_BRANCH,
        "reply_limit": MAX_REPLIES,
        "exchange_nodes": MAX_EXCHANGE_NODES,
        "exchange_plies": MAX_EXCHANGE_PLIES,
        "minimum_gain": 3,
        "root_order": "recorded-newest-first-alternatives-oldest-first-v1",
    }
    return {**identity, "version": VERSION, "policy": {**identity["policy"], "pin": pin}}
