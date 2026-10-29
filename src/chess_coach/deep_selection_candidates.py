"""Reconstruct learner decisions and nominate possible reasons for selection."""

from .analysis_positions import decisions
from .deep_selection_reasons import decision_reasons


def candidates(db, source, cp_gap, wdl_gap):
    by_position = {}
    for line in source["lines"]:
        by_position.setdefault(line["position_id"], {})[line["role"]] = line
    result = []
    for position, board in decisions(db.connection, source["game"]):
        mover = "white" if board.turn else "black"
        if mover != source["color"]:
            continue
        result.append(
            {
                "position_id": position["id"],
                "ply": position["ply"],
                "fen": board.fen(),
                "reasons": decision_reasons(
                    position, board, by_position.get(position["id"], {}), cp_gap, wdl_gap
                ),
            }
        )
    return result
