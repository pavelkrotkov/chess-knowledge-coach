"""Qualify compared roots under one bounded report-wide protection allocation."""

import time

import chess

from .style_guard_exchange import assess
from .style_guard_inspect import NODE_LIMIT, VERSION
from .style_protection_budget import take
from .style_protection_proof import PROOF_SECONDS
from .style_schedule_budget import BudgetExceeded, consume


def qualify(board, target, before, roots, evidence, provenance, budget):
    # All roots share one node counter and the existing one-second proof ceiling.
    start = time.monotonic()
    nodes = [0]

    def check():
        consume()
        if time.monotonic() - start >= PROOF_SECONDS:
            raise TimeoutError

    def node():
        check()
        if nodes[0] >= NODE_LIMIT:
            raise BudgetExceeded("exchange limit")

    results = {}
    for root in roots:
        # Keep the final work unit available for the original source recheck.
        if budget["used"] >= budget["limit"] - 1:
            budget["skipped"] += 1
            budget["exchange_unknown"] += 1
            results[root] = {"status": "unknown", "reason": "report_budget_exhausted"}
            continue
        if not take(budget, "proofs"):
            budget["exchange_unknown"] += 1
            results[root] = {"status": "unknown", "reason": "report_budget_exhausted"}
            continue
        budget["exchange_examined"] += 1
        try:
            check()
            move = chess.Move.from_uci(root)
            result = assess(
                board, move, target, time.monotonic, start, PROOF_SECONDS, nodes, check, node
            )
        except (ValueError, TypeError, TimeoutError, BudgetExceeded):
            result = {"status": "unknown", "reason": "exchange_incomplete"}
        if result["status"] == "supported":
            result.update(_binding(board, move, target, before, evidence, provenance))
        else:
            budget["exchange_unknown"] += 1
        results[root] = result
    budget["exchange_nodes"] += nodes[0]
    return results


def _binding(board, move, target, before, evidence, provenance):
    attackers = {chess.Move.from_uci(uci).from_square for uci in before["targets"][target]}
    return {
        "version": VERSION,
        "evidence_id": evidence,
        "source_target": chess.square_name(target),
        "target_piece": chess.piece_name(board.piece_type_at(target)),
        "moved_target": move.from_square == target,
        "captured_attacker": board.is_capture(move) and move.to_square in attackers,
        "source": {
            key: provenance[key]
            for key in ("review_status", "review_event_id", "objective_version", "history_mode")
        },
    }
