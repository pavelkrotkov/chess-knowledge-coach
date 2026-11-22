"""Bind a combined capture-and-fork preparation without invalidating v1."""

import chess

from .fact_fingerprint import canonical, digest
from .fork_contract import VERSION as FORK_VERSION
from .fork_proof import MAX_REPLIES
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .objective_fork_contract import VERIFIER
from .opening_full_history_build import TRANSFORM
from .opening_public_proof_files import latest

VERSION = "public-opening-capture-fork-preparation-v2"
ROOTS_PER_GAME = 64
PROOFS_PER_BRANCH = 8


def combined(identity):
    policy = {
        **identity["policy"],
        "fork": {
            "producer": FORK_VERSION,
            "execution_contract": VERIFIER,
            "kernel": "fork_proof",
            "mate_rule": "legal-move-then-checkmate-v1",
            "objective": "named_fork_material_or_immediate_mate",
            "minimum_gain": 3,
            "reply_limit": MAX_REPLIES,
            "exchange_nodes": MAX_EXCHANGE_NODES,
            "exchange_plies": MAX_EXCHANGE_PLIES,
            "root_order": "recorded-first-reverse-position-legal-order-v1",
            "chess_version": chess.__version__,
            "roots_per_game": ROOTS_PER_GAME,
            "proofs_per_branch": PROOFS_PER_BRANCH,
        },
    }
    return {**identity, "version": VERSION, "policy": policy}


def continuation(identity, sha):
    value = combined(identity)
    fork = {
        **value["policy"]["fork"],
        "window": "continuation",
        "offset": 36,
        "positions": 36,
        "index_sha256": sha,
        "transform": TRANSFORM,
    }
    return {
        **value,
        "version": "public-opening-capture-fork-continuation-v3",
        "policy": {**value["policy"], "fork": fork},
    }


def _read(directory, identity):
    value = latest(directory, digest(canonical(identity)))
    if value is not None and (
        value.get("version") != identity["version"] or value.get("binding") != identity
    ):
        raise ValueError("public preparation unavailable")
    return value


def current(directory, identity, *, chosen=None, capture_only=False):
    newer = None if capture_only else _read(directory, chosen or combined(identity))
    if newer is None:
        return _read(directory, identity), None
    try:
        older = _read(directory, identity)
    except (OSError, ValueError, TypeError, KeyError):
        older = None
    return newer, older
