"""Describe verified choices without attributing intent or mastery."""

import chess


def explain(prepared):
    fact, report = prepared["fact"], prepared["report"]
    board = chess.Board(report["decision_fen"])
    targets = [
        chess.square_name(chess.square(chess.square_file(sq), 7 if board.color_at(sq) else 0))
        for sq in chess.scan_forward(board.pawns)
    ]
    return {
        "outcome": fact["outcome"],
        "reason": fact["reason"],
        "root": fact["root_wdl"],
        "played": report["played"],
        "preserving": [m["san"] for m in fact["preserving"]],
        "worse": [m["san"] for m in fact["worse"]],
        "targets": targets,
        "geometry": report["proof"].get("geometry"),
    }
