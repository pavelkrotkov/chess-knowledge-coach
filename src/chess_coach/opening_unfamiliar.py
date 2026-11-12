"""Offer a source-backed first-turn experiment without recording activity."""

import time

import chess

from .learner_identity import normalize_identity
from .opening_explore_recent import recent
from .opening_queue_budget import BrowserBudget
from .opening_snapshot import SOURCE as CATALOG_SOURCE
from .opening_storage import position_key
from .opening_unfamiliar_history import seen
from .opening_unfamiliar_public import public
from .opening_unfamiliar_sample import sample
from .opening_unfamiliar_sources import catalog_dataset, choices, common_black


def _select(db, root, subject, dataset, board, color, budget):
    parent = position_key(board)
    with budget.scope(snapshot=True):
        options = choices(db, dataset, board)
    for item in options:
        reference = public(root, subject, parent, item["uci"], budget)
        if not reference:
            continue
        with budget.scope(snapshot=True):
            familiar = seen(db, subject, item, color, parent)
        if not familiar:
            line, data = reference
            return {**item, "line": line, "profile": data}
    budget.check()
    return None


def explore_unfamiliar(db, root, learner):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + 25)
    subject = normalize_identity(learner)
    db.connection.create_function(
        "normalized_opening_owner", 1, normalize_identity, deterministic=True
    )
    with budget.scope(snapshot=False):
        games, coverage = recent(db, learner)
    white, black, failed, sample_identity = sample(db, learner, games, budget)
    first, count = common_black(black)
    with budget.scope(snapshot=True):
        dataset = catalog_dataset(db)
    board = chess.Board()
    white_choice = _select(db, root, subject, dataset, board, "white", budget) if white else None
    parent_san = board.san(board.parse_uci(first)) if first else None
    if first:
        board.push_uci(first)
    black_choice = _select(db, root, subject, dataset, board, "black", budget) if first else None
    budget.check()
    return {
        "catalog_source": CATALOG_SOURCE,
        "sample_identity": sample_identity,
        "sample": len(games),
        "coverage": coverage,
        "failed": failed,
        "white_count": len(white),
        "black_count": len(black),
        "parent": parent_san,
        "parent_count": count,
        "white": white_choice,
        "black": black_choice,
    }
