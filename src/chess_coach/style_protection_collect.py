"""Bind a target and qualify every comparable response within a work budget."""

import chess

from .style_protection_proof import original, proof
from .style_protection_source import load, recheck


def collect(db, learner, context, board, compared, evidence, budget):
    source = load(db, learner, evidence, budget)
    if source is None or source["provenance"]["position_id"] != context["position_id"]:
        return None
    target = chess.parse_square(source["provenance"]["objective_target"])
    before = original(board, target, budget)
    if before is None:
        return None
    results = _qualify(board, target, before, evidence, compared, budget)
    if not recheck(db, learner, evidence, source["provenance"], budget):
        return None
    _attach_source(results, source["provenance"])
    return results


def _qualify(board, target, before, evidence, compared, budget):
    roots = [
        compared["played"]["root_move"],
        *(p["alternative_line"]["root_move"] for p in compared["pairs"]),
    ]
    return {
        root: proof(board, root, target, before, evidence, budget) for root in dict.fromkeys(roots)
    }


def _attach_source(results, provenance):
    for result in results.values():
        if result["status"] == "supported":
            result["source"] = {
                key: provenance[key]
                for key in ("review_status", "review_event_id", "objective_version", "history_mode")
            }
