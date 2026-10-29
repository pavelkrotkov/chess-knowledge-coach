"""Check the cited fork targets on the resulting board."""

import chess


def fork(evidence, fen):
    note = evidence.get("fork_explanation") or {}
    board = chess.Board(fen)
    try:
        move = board.parse_san(note["move"])
        board.push(move)
        square = move.to_square
        targets = sorted({chess.parse_square(s) for s in note["targets"]})
        valid = [s for s in targets if _target(board, square, s)]
        if len(valid) < 2:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError("fork proof unavailable") from None
    return {
        "version": "lesson-probe-v1",
        "operation": "recognize",
        "fen": board.fen(),
        "question": f"The piece on {chess.square_name(square)} just moved. Name one square of an opposing piece it attacks.",
        "accepted": [chess.square_name(s) for s in valid],
        "basis": "Checked targets of the cited fork after its legal move",
        "familiarity": "cued and familiar",
    }


def _target(board, square, target):
    return board.color_at(target) == board.turn and target in board.attacks(square)
