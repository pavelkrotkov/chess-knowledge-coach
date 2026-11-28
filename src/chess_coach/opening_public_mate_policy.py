"""Bind an immediate-mate preparation to its exact full-history source."""

import time

import chess

from .objective_contract import OBJECTIVE
from .opening_full_history_build import TRANSFORM
from .opening_public_fork_windows import WINDOW
from .opening_public_proof_source import MAX_GAMES

VERSION = "public-opening-immediate-mate-v1"


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("public mate deadline")


def policy(identity, sha, window):
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid mate window")
    mate = {
        "objective": OBJECTIVE,
        "version": VERSION,
        "window": window,
        "positions": WINDOW,
        "games_per_branch": MAX_GAMES,
        "index_sha256": sha,
        "transform": TRANSFORM,
        "chess_version": chess.__version__,
        "alternatives": "all-legal-immediate-mates",
    }
    return {**identity, "version": VERSION, "policy": {**identity["policy"], "mate": mate}}
