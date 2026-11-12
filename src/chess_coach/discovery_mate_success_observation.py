"""Check a played immediate defense against an independently witnessed mate."""

import time

from .discovery_mate_success_probe import candidates
from .discovery_mate_success_scope import terminal_after, unsupported
from .discovery_mate_success_witness import witness
from .material_ambiguity import ambiguous
from .objective_defense_judge import judge

SECONDS = 1.0


def observe(board, played, best_line, played_line, *, started=None):
    started = time.monotonic() if started is None else started

    def check():
        if time.monotonic() - started >= SECONDS:
            raise TimeoutError

    try:
        return _observe(board, played, started, check)
    except TimeoutError:
        return ambiguous("discovery_mate_success", "proof_deadline_exhausted")


def _observe(board, played, started, check):
    if unsupported(board):
        return ambiguous("discovery_mate_success", "history_or_position_unavailable")
    try:
        actual = board.parse_uci(played)
    except (ValueError, TypeError):
        return ambiguous("discovery_mate_success", "played_move_unavailable")
    if terminal_after(board, actual):
        return ambiguous("discovery_mate_success", "played_terminal_or_claimable")
    check()
    nominated = candidates(board, check)
    if nominated is None:
        return ambiguous("discovery_mate_success", "nomination_limit_or_unavailable")
    if not nominated:
        return None
    answer = judge(board.copy(), actual, time.monotonic, started, SECONDS, {})
    if answer["status"] != "correct":
        return ambiguous(
            "discovery_mate_success", answer.get("reason", "played_defense_unresolved")
        )
    anchor, reason = witness(board, actual, nominated, check)
    if not anchor:
        return ambiguous("discovery_mate_success", reason)
    check()
    return {
        "kind": "discovery_mate_success",
        "outcome": "success",
        "played": {"move": actual.uci(), "san": board.san(actual)},
        "witness": anchor,
        "threat": anchor["proof"],
        "defense": {
            "move": actual.uci(),
            "san": board.san(actual),
            "legal_replies": answer["legal_replies"],
        },
        "boundary": "The opponent-turn probe nominates geometry only. A different legal quiet move then permits the proved mate. The played defense avoids all immediate mates; later consequences and intent remain unknown.",
    }
