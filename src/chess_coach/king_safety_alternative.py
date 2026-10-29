"""Select a comparator from a small, explicitly bounded set of legal moves."""

from .king_safety_scan import scan

MAX_ALTERNATIVES = 8


def _rank(item):
    return (sum(c["mate"] for c in item["checks"]), len(item["checks"]), item["move"]["uci"])


def alternatives(board, played):
    moves = [m for m in sorted(board.legal_moves, key=lambda m: m.uci()) if m != played]
    options = [scan(board, m) for m in moves[:MAX_ALTERNATIVES]]
    complete = [item for item in options if item["status"] == "complete"]
    return {
        "selected": min(complete, key=_rank) if complete else None,
        "examined": len(options),
        "legal_count": len(moves),
        "unresolved": len(options) - len(complete),
    }
