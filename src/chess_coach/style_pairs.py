"""Build equal-horizon scored alternatives for a selected root."""

from .style_center_lines import events
from .style_metrics import endpoint, metrics
from .style_score import score_ok

SCORE_BAND = 50


def pairs(board, chosen, chosen_board, lines):
    pairs = []
    root_metrics = metrics(board, board.turn)
    played_metrics = {**metrics(chosen_board, board.turn), "center_events": events(board, chosen)}
    for line in lines:
        if line["root_move"] == chosen["root_move"]:
            continue
        if not score_ok(line):
            return [], "alternative_score_unusable"
        if abs(line["score_value"] - chosen["score_value"]) > SCORE_BAND:
            continue
        if line["depth"] != chosen["depth"]:
            return [], "unequal_search_depth"
        other_board = endpoint(board, line)
        if other_board is None:
            return [], "short_or_invalid_pv"
        pairs.append(
            {
                "root": root_metrics,
                "played": played_metrics,
                "alternative": {
                    **metrics(other_board, board.turn),
                    "center_events": events(board, line),
                },
                "alternative_line": line,
            }
        )
    return pairs, None


def pair_result(found, rejected, chosen, result):
    status = rejected or ("comparable" if found else "no_similar_alternative")
    return {"status": status, "pairs": [] if rejected else found, "played": chosen, "run": result}
