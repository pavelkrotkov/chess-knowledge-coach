"""Render a versioned illustrative line from a current fork certificate."""

import chess

from .course_pgn import chapter
from .related_fork_witness import witness
from .tactical_course_presentation import VERSION


def _illustration(snapshot):
    board = chess.Board(snapshot["prompt_fen"])
    proof = snapshot["provenance"]["fork_certificate"]
    line = witness(board.fen(), proof)
    targets = []
    for square in proof["targets"]:
        piece = board.piece_at(chess.parse_square(square))
        if piece is None or piece.color == board.turn:
            raise ValueError("fork target unavailable")
        targets.append(f"{chess.piece_name(piece.piece_type)} on {square}")
    if len(targets) < 2 or proof["minimum_gain"] != 3:
        raise ValueError("fork certificate unavailable")
    target_list = ", ".join(targets)
    explanation = (
        f"The fork attacks the {target_list}. This defense is one illustrative reply, "
        "not necessarily best or forced. The certificate checks all immediate defenses and "
        "a target capture with bounded replies and exchanges, establishing at least three "
        "material units within those bounds. Longer play and other teaching lines are ungraded."
    )
    return {"version": VERSION, "lines": [line]}, explanation


def build(note, snapshot, source):
    presentation, explanation = _illustration(snapshot)
    note = note.replace(
        "This is a recorded line, not a mastery result.", "This is not a mastery result."
    )
    color = snapshot["learner_color"].capitalize()
    guidance = f"Worked example, ungraded. {color} to move. {note} {explanation}"
    result = chapter(
        "Your recurring pattern",
        note,
        {**snapshot, "lines": presentation["lines"]},
        source,
        guidance=guidance,
    )
    result["source_snapshot"] = snapshot
    result["presentation"] = presentation
    return result
