"""Validate one persisted variation against the bound decision."""


def line(line, board):
    moves = (line.get("pv") or "").split()
    if not moves or len(moves) > 100 or moves[0] != line["root_move"]:
        return False
    return _identity(line, board)


def _identity(line, board):
    return (
        line.get("semantics") == "same-board-roots-v1"
        and line.get("role") == "candidate"
        and line.get("decision_fen") == board.fen()
        and line.get("score_pov") == ("white" if board.turn else "black")
    )
