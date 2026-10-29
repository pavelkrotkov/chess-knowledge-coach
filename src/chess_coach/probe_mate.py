"""Identify checking pieces after a cited, replayable proved move."""

import chess


def mate(evidence, fen):
    payload = evidence["facts"][0]["payload"]
    roots = (payload.get("proof") or {}).get("alternatives") or []
    for root in roots:
        if root.get("status") != "proved":
            continue
        board = _checked_board(fen, (root.get("move") or {}).get("san"))
        if board is not None:
            return {
                "version": "lesson-probe-v1",
                "operation": "recognize",
                "fen": board.fen(),
                "question": "Which square holds a piece checking the king? Name one square.",
                "accepted": sorted(chess.square_name(s) for s in board.checkers()),
                "basis": "Checking pieces after a legal move in the cited mating proof",
                "familiarity": "cued and familiar",
            }
    raise ValueError("no checking move in cited proof")


def _checked_board(fen, san):
    try:
        board = chess.Board(fen)
        board.push(board.parse_san(san))
        return board if board.is_check() else None
    except (ValueError, TypeError):
        return None
