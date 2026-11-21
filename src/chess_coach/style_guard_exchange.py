"""Inspect every legal capture of the named piece with a shared work budget."""

import chess

from .material_exchange import exchange
from .style_guard_scope import prepare
from .style_guard_witness import guard, reply_witness


def assess(board, move, target, clock, start, seconds, budget, check, node):
    prepared, issue = prepare(board, move, target, clock, start, seconds, check)
    if issue:
        return {"status": "unknown", "reason": issue}
    after, square, named = prepared
    return _captures(board, after, move, square, named, budget, check, node)


def _captures(board, after, move, square, named, budget, check, node):
    options = [m for m in after.legal_moves if after.is_capture(m) and m.to_square == square]
    captures = []
    for attack in options:
        check()
        gain = exchange(after, attack, budget=budget, check=node)
        if gain is None:
            return {
                "status": "unknown",
                "reason": "exchange_unresolved",
                "target_captures": {"available": len(options), "examined": len(captures)},
            }
        if gain > 0:
            captures.append({"capture": attack.uci(), "opponent_gain": gain})
            return {
                "status": "unknown",
                "reason": "positive_opponent_gain",
                "captures": captures,
                "target_captures": {"available": len(options), "examined": len(captures)},
            }
        witness = reply_witness(after, square, attack, budget, node)
        captures.append(
            {
                "capture": attack.uci(),
                "opponent_gain": gain,
                "recapture": witness["recapture"],
                "recapture_gain_max": witness["opponent_gain_max"],
            }
        )
    witness = guard(board, after, move, square, named, options, budget, node)
    return {
        "status": "supported",
        "target": chess.square_name(square),
        "captures": captures,
        "target_captures": {"available": len(options), "examined": len(captures)},
        "opponent_gain_max": max([0, *(entry["opponent_gain"] for entry in captures)]),
        "guard_witness": witness,
    }
