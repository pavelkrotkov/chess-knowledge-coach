"""Compose source-qualified mate teaching and ungraded unfamiliar rehearsal."""

import chess

from .course_pgn import chapter
from .tactical_course_display import _note


def explanation(owned):
    snapshot = owned["source_snapshot"]
    board = chess.Board(snapshot["prompt_fen"])
    move = board.parse_uci(snapshot["lines"][0].split()[0])
    objective = snapshot["objective"]
    if objective == "mate_in_one":
        checked = board.copy()
        checked.push(move)
        if not checked.is_checkmate():
            raise ValueError("mate source changed")
        result = f"The shown move {board.san(move)} checkmates immediately."
    elif objective == "mate_within_two":
        result = f"The shown move {board.san(move)} starts a forced mate within two of your moves."
    else:
        raise ValueError("mate objective unavailable")
    review = snapshot["provenance"]["review_status"]
    note = f"Provisional recurring observation. This source review is {review}."
    color = snapshot["learner_color"].capitalize()
    guidance = (
        f"{color} to move. {result} {note} "
        "Follow the next chapter for the owned example; this is not a mastery result."
    )
    return {
        **chapter("Understand the mating idea", note, snapshot, owned["source"], guidance=guidance),
        "role": "explanation",
    }


def rehearsal(practice):
    snapshot = practice["source_snapshot"]
    board = chess.Board(snapshot["prompt_fen"])
    note = _note(practice, board)
    color = snapshot["learner_color"].capitalize()
    qualification = "Other mating moves may also work."
    if len(snapshot["lines"][0].split()) > 1:
        qualification = "The supplied line is not a proof against every defense."
    guidance = (
        f"Ungraded rehearsal. {color} to move. "
        f"Try to find mate, then reveal the supplied line. {qualification} "
        "Other moves are not graded here. "
        f"{note} Use the local related-mate practice to explore alternatives. "
        "Study activity does not update your coach practice record."
    )
    return {
        **chapter("Practice a mating idea", note, snapshot, practice["source"], guidance=guidance),
        "role": "practice",
    }


def compose(owned, practice):
    result = [explanation(owned), {**owned, "role": "worked"}]
    if practice is not None:
        result.append(rehearsal(practice))
    return result
