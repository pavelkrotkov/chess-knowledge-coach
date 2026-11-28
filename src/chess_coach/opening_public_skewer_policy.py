"""Bind a royal-skewer preparation to its exact full-history source."""

import chess

from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES, MIN_GAIN
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES
from .skewer_game_proof import MAX_ROOTS
from .skewer_game_proof import VERSION as PROOF_VERSION

VERSION = "public-opening-royal-skewer-v1"


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid skewer window")
    skewer = {
        "objective": "royal_skewer",
        "version": VERSION,
        "proof_version": PROOF_VERSION,
        "window": window,
        "positions": WINDOW,
        "games_per_branch": MAX_GAMES,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
        "root_limit": MAX_ROOTS,
        "reply_limit": MAX_REPLIES,
        "exchange_nodes": MAX_EXCHANGE_NODES,
        "exchange_plies": MAX_EXCHANGE_PLIES,
        "minimum_gain": MIN_GAIN,
        "scope": "first-supported-checking-root",
    }
    return {**identity, "version": VERSION, "policy": {**identity["policy"], "skewer": skewer}}
