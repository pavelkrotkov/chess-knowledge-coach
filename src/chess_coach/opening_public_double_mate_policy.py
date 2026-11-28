"""Bind a double-check mate preparation to its exact full-history source."""

import chess

from .discovery_contract import MAPPER, PRODUCER, SCOPE
from .discovery_contract import VERSION as DISCOVERY_VERSION
from .objective_contract import OBJECTIVE
from .objective_contract import VERSION as MATE_VERSION
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES

VERSION = "public-opening-double-check-mate-v1"


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid double-check mate window")
    double_mate = {
        "objective": OBJECTIVE,
        "version": VERSION,
        "mate_version": MATE_VERSION,
        "producer": PRODUCER,
        "mapper": MAPPER,
        "discovery_version": DISCOVERY_VERSION,
        "scope": SCOPE,
        "operation": "execute",
        "window": window,
        "positions": WINDOW,
        "games_per_branch": MAX_GAMES,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
        "alternatives": "all-legal-double-check-immediate-mates",
    }
    return {
        **identity,
        "version": VERSION,
        "policy": {**identity["policy"], "double_mate": double_mate},
    }
