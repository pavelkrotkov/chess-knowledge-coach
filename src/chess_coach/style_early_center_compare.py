"""Compare one current early control's played and selected roots."""

from .style_center_capture import capture
from .style_compare import candidates
from .style_early_center import eligible
from .style_history_lines import history_safe, lines_safe


def observation(context, slot, snapshot, view):
    board = snapshot["board"]
    if not history_safe(board) or not eligible(board, context["ply"]):
        return "unsupported", None
    attempt = view["attempts"][-1]
    alternatives = [{"rank": item["rank"], "line": item} for item in attempt["final"]["lines"]]
    compared = candidates(
        board,
        context["played_move"],
        {"status": "complete", "result": {"alternatives": alternatives}},
    )
    if compared["status"] != "comparable":
        return "unsupported", None
    other = compared["pairs"][0]["alternative_line"]
    if not lines_safe(board, [compared["played"], other]):
        return "unsupported", None
    played = board.parse_uci(compared["played"]["root_move"])
    alternate = board.parse_uci(other["root_move"])
    left, right = _central(board, played), _central(board, alternate)
    if left == right:
        return "no_contrast", None
    return "admitted", {
        "game_id": context["game_id"],
        "position_id": context["position_id"],
        "ply": context["ply"],
        "request_id": slot["request_id"],
        "cycle": slot["sequence"],
        "attempt_number": attempt["number"],
        "played": board.san(played),
        "alternative": board.san(alternate),
        "choice": "played_capture" if left else "alternative_capture",
    }


def _central(board, move):
    result = capture(board, move, 1)
    return bool(result and result["central"])
