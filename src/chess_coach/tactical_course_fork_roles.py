"""Explain one source-qualified knight fork without changing its proof."""

import chess

from .course_pgn import chapter
from .tactical_course_fork_chapter import _illustration


def explanation(owned):
    snapshot = owned["source_snapshot"]
    board = chess.Board(snapshot["prompt_fen"])
    move = board.parse_uci(snapshot["lines"][0])
    mover = board.piece_at(move.from_square)
    if mover is None or mover.piece_type != chess.KNIGHT:
        raise ValueError("knight fork source unavailable")
    _, details = _illustration(snapshot)
    status = snapshot["provenance"]["review_status"]
    note = f"Provisional recurring observation. This source review is {status}."
    guidance = (
        f"{snapshot['learner_color'].capitalize()} to move. The knight on "
        f"{chess.square_name(move.from_square)} can play {board.san(move)} to attack "
        f"more than one valuable target. {details} {note} "
        "Follow the next chapter for the recorded example; this is not a mastery result."
    )
    result = chapter(
        "Understand your knight fork", note, snapshot, owned["source"], guidance=guidance
    )
    return {**result, "role": "explanation"}


def compose(owned, practice, budget, enabled):
    if not enabled:
        return [owned] if practice is None else [owned, practice]
    with budget.scope(snapshot=False):
        result = [explanation(owned), {**owned, "role": "worked"}]
    if practice is not None:
        result.append({**practice, "role": "practice"})
    return result
