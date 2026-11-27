"""Explain and group the source-bound roles of a named capture lesson."""

import chess

from .course_pgn import chapter
from .tactical_course_display import _note


def explanation(owned):
    snapshot = owned["source_snapshot"]
    if (
        snapshot["objective"] != "capture_named_target"
        or snapshot["provenance"]["gain_threshold"] != 3
    ):
        raise ValueError("named capture objective unavailable")
    board = chess.Board(snapshot["prompt_fen"])
    move = board.parse_uci(snapshot["lines"][0])
    target = chess.parse_square(snapshot["provenance"]["objective_target"])
    piece, mover = board.piece_at(target), board.piece_at(move.from_square)
    if not piece or not mover or move.to_square != target or not board.is_capture(move):
        raise ValueError("named capture source changed")
    note = _note(owned, board)
    guidance = (
        f"{snapshot['learner_color'].capitalize()} to move. Your {chess.piece_name(mover.piece_type)} "
        f"can take the {chess.piece_name(piece.piece_type)} on {chess.square_name(target)} "
        f"with {board.san(move)}. The bounded check establishes a net gain of at least three "
        "material points in the replies checked; it is not a full evaluation. "
        f"{note} Follow the next chapter to reveal the recorded example."
    )
    result = chapter("Understand your capture", note, snapshot, owned["source"], guidance=guidance)
    return {**result, "role": "explanation"}


def compose(choice, owned, practice, enabled):
    if enabled and choice["kind"] == "capture":
        result = [explanation(owned), {**owned, "role": "worked"}]
        if practice is not None:
            result.append({**practice, "role": "practice"})
        return result
    return [owned] if practice is None else [owned, practice]
