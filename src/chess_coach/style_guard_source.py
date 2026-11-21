"""Resolve and recheck one owned protection source inside its snapshot."""

import time

import chess

from .learner_identity import normalize_identity
from .objective_protection_contract import VERSION as SOURCE_VERSION
from .objective_protection_source import resolve_details
from .style_guard_exchange import assess
from .style_protection_source import recheck


def inspect_source(db, learner, evidence_id, response, history, nodes, check, node, start, seconds):
    row = db.connection.execute(
        "SELECT p.game_id,e.position_id FROM evidence_mappings e JOIN positions p ON p.id=e.position_id WHERE e.id=? AND e.subject=?",
        (evidence_id, normalize_identity(learner)),
    ).fetchone()
    if row is None:
        raise ValueError("source unavailable")
    history.targets([row["position_id"]])
    board = history.board(row["game_id"], row["position_id"])
    source, _, board = resolve_details(
        db, SOURCE_VERSION, str(evidence_id), learner, _verified_board=board, _history=history
    )
    target = chess.parse_square(source["provenance"]["objective_target"])
    move = chess.Move.from_uci(response)
    result = assess(board, move, target, time.monotonic, start, seconds, nodes, check, node)
    check()
    from .style_protection_budget import create

    if not recheck(db, learner, evidence_id, source["provenance"], create(), history=history):
        raise ValueError("source unavailable")
    check()
    result["response"] = move.uci()
    result["source"] = {
        key: source["provenance"][key]
        for key in ("objective_version", "history_mode", "review_status", "review_event_id")
    }
    result["source"]["evidence_id"] = evidence_id
    return result
