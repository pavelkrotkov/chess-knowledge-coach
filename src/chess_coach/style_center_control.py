"""Describe current non-check control contrasts without inferring style fit."""

from .style_center import classify
from .style_compare import candidates
from .style_context import describe_context
from .style_history_lines import history_safe, lines_safe
from .style_opening import current_opening

DIMENSION = "center_file_opening"


def observation(db, context, slot, snapshot, view):
    board = snapshot["board"]
    if not history_safe(board):
        return "unavailable", None
    attempt = view["attempts"][-1]
    lines = attempt["final"]["lines"]
    alternatives = [{"rank": item["rank"], "line": item} for item in lines]
    compared = candidates(
        board,
        context["played_move"],
        {"status": "complete", "result": {"alternatives": alternatives}},
    )
    if compared["status"] != "comparable":
        return "unavailable", None
    inspected = [compared["played"], *(pair["alternative_line"] for pair in compared["pairs"])]
    if not lines_safe(board, inspected):
        return "unavailable", None
    value = classify(compared["pairs"][0])[DIMENSION]
    if value not in ("file_opened", "file_still_occupied"):
        return ("ambiguous" if value == "ambiguous" else "no_contrast"), None
    return "admitted", {
        "game_id": context["game_id"],
        "position_id": context["position_id"],
        "ply": context["ply"],
        "played_move": context["played_move"],
        "game_outcome": context["game_outcome"],
        "context": describe_context(db, context, current_opening(db, context["game_id"])),
        "allocation": "purpose_control",
        "provenance": "purpose_center_control",
        "request_id": slot["request_id"],
        "attempt_number": attempt["number"],
        "cycle": slot["sequence"],
        "choices": {DIMENSION: value},
        "pairs": compared["pairs"],
        "played_line": compared["played"],
        "limits": view["limits"],
        "legal_roots": board.legal_moves.count(),
        "ranked_roots": len(alternatives),
    }
