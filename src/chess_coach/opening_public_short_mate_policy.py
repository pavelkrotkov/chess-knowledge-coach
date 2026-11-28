"""Bind a short-mate preparation to an immutable full-history source."""

import chess

from .mate_proof import MAX_NODES
from .mate_proof import VERSION as PROOF_VERSION
from .mate_proof_search import MAX_REPLIES
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES

VERSION = "public-opening-short-mate-v1"


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid short-mate window")
    short_mate = {
        "objective": "mate_within_two",
        "version": VERSION,
        "proof_version": PROOF_VERSION,
        "window": window,
        "positions": WINDOW,
        "games_per_branch": MAX_GAMES,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
        "plies": 3,
        "nodes": MAX_NODES,
        "reply_limit": MAX_REPLIES,
        "alternatives": "all-legal-roots-with-status",
    }
    return {
        **identity,
        "version": VERSION,
        "policy": {**identity["policy"], "short_mate": short_mate},
    }
