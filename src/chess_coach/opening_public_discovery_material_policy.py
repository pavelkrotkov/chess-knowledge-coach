"""Bind recorded public discoveries to the existing execution proof."""

import chess

from .discovery_contract import MAPPER, PRODUCER, SCOPE
from .discovery_contract import VERSION as DISCOVERY_VERSION
from .discovery_proof import MAX_REPLIES
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES

VERSION = "public-opening-discovery-material-recorded-v1"


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid discovery material window")
    material = {
        "version": VERSION,
        "producer": PRODUCER,
        "mapper": MAPPER,
        "discovery_version": DISCOVERY_VERSION,
        "scope": SCOPE,
        "operation": "execute",
        "root_scope": "recorded",
        "minimum_gain": 3,
        "reply_limit": MAX_REPLIES,
        "exchange_nodes": MAX_EXCHANGE_NODES,
        "exchange_plies": MAX_EXCHANGE_PLIES,
        "window": window,
        "positions": WINDOW,
        "games_per_branch": MAX_GAMES,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
    }
    return {
        **identity,
        "version": VERSION,
        "policy": {**identity["policy"], "discovery_material": material},
    }
