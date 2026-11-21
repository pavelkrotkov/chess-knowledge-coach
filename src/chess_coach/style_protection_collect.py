"""Bind a target and qualify every comparable response within a work budget."""

import chess

from .style_protection_exchange import qualify
from .style_protection_proof import original, proof
from .style_protection_source import load, recheck


def collect(db, learner, context, board, compared, evidence, budget, *, source=None, history=None):
    if source is None:
        source = load(
            db,
            learner,
            evidence,
            budget,
            verified_board=board if history else None,
            history=history,
        )
    if source is None or source["provenance"]["position_id"] != context["position_id"]:
        return None
    target = chess.parse_square(source["provenance"]["objective_target"])
    before = original(board, target, budget)
    if before is None:
        return None
    results = _qualify(board, target, before, evidence, compared, budget)
    exchange = qualify(board, target, before, list(results), evidence, source["provenance"], budget)
    for root, result in results.items():
        result["exchange"] = exchange[root]
    current = recheck(db, learner, evidence, source["provenance"], budget, history=history)
    _account_exchange(budget, exchange, current)
    if not current:
        return None
    _attach_source(results, source["provenance"])
    return results


def _account_exchange(budget, exchange, current):
    # A source that changed during proof cannot count as a supported result.
    count = sum(item["status"] == "supported" for item in exchange.values())
    budget["exchange_supported" if current else "exchange_unknown"] += count


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
