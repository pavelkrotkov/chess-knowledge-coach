"""Use only result-preserving choices in the cited pawn proof."""

import chess


def pawn(evidence, fen):
    note = evidence.get("pawn_explanation") or {}
    board = chess.Board(fen)
    choices = []
    for san in note.get("preserving", []):
        try:
            move = board.parse_san(san)
            choices.append(board.san(move))
        except (ValueError, TypeError):
            continue
    if not choices:
        raise ValueError("pawn proof unavailable")
    return {
        "version": "lesson-probe-v1",
        "operation": "evaluate",
        "fen": fen,
        "question": "Choose a legal move that preserves the proved result of this pawn ending (use chess notation).",
        "accepted": sorted(set(choices)),
        "basis": "Cited bounded pawn proof, result-preserving choices",
        "familiarity": "cued and familiar",
    }
