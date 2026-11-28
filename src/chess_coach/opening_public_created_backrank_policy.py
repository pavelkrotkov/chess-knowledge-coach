"""Bind newly allowed back-rank defense to an immutable public source."""

import chess

from .back_rank_contract import MAPPER, PRODUCER
from .back_rank_contract import VERSION as CLASSIFIER_VERSION
from .back_rank_defense import MAX_NODES
from .back_rank_defense import VERSION as OBSERVER_VERSION
from .back_rank_scan import MAX_MOVES
from .objective_defense_judge import VERSION as JUDGE_VERSION
from .objective_defense_scan import MAX_NODES as JUDGE_NODES
from .objective_defense_snapshot import OBJECTIVE
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES

VERSION = "public-opening-created-backrank-defense-v1"


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid created back-rank window")
    defense = {
        "version": VERSION,
        "producer": PRODUCER,
        "mapper": MAPPER,
        "classifier_version": CLASSIFIER_VERSION,
        "observer_version": OBSERVER_VERSION,
        "judge_version": JUDGE_VERSION,
        "objective": OBJECTIVE,
        "operation": "prevent",
        "origin": "newly_allowed",
        "observer_node_limit": MAX_NODES,
        "observer_reply_limit": MAX_MOVES,
        "judge_node_limit": JUDGE_NODES,
        "judge_reply_limit": MAX_MOVES,
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
        "policy": {**identity["policy"], "created_backrank": defense},
    }
