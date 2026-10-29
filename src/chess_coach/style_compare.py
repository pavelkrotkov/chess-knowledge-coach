"""Gate one current complete MultiPV choice."""

from .style_metrics import endpoint
from .style_pairs import pair_result, pairs
from .style_score import chosen


def candidates(board, played, deep):
    if deep is None:
        return {"status": "not_selected", "pairs": []}
    if deep["status"] != "complete":
        return {"status": deep["status"], "pairs": []}
    result = deep["result"]
    lines = [item["line"] for item in result["alternatives"]]
    if len(lines) < 2:
        status = "forced_move" if board.legal_moves.count() == 1 else "single_root_search"
        return {"status": status, "pairs": []}
    chosen_line, issue = chosen(lines, played)
    if issue:
        return {"status": issue, "pairs": []}
    chosen_board = endpoint(board, chosen_line)
    if chosen_board is None:
        return {"status": "short_or_invalid_pv", "pairs": []}
    found, rejected = pairs(board, chosen_line, chosen_board, lines)
    return pair_result(found, rejected, chosen_line, result)
