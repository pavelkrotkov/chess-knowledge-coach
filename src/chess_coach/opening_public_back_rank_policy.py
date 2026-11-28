"""Bind a public back-rank mate preparation to a full-history source."""

import chess

from .back_rank_contract import VERSION as CLASSIFIER_VERSION
from .objective_contract import OBJECTIVE
from .objective_contract import VERSION as PROOF_VERSION
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES

VERSION = "public-opening-back-rank-mate-v1"


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid back-rank window")
    back_rank = {
        "objective": OBJECTIVE,
        "version": VERSION,
        "proof_version": PROOF_VERSION,
        "classifier": "back_rank_terminal.terminal",
        "classifier_version": CLASSIFIER_VERSION,
        "window": window,
        "positions": WINDOW,
        "games_per_branch": MAX_GAMES,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
        "alternatives": "all-legal-back-rank-immediate-mates",
    }
    return {
        **identity,
        "version": VERSION,
        "policy": {**identity["policy"], "back_rank": back_rank},
    }
