"""Render an admitted named capture using the faithful Study mode."""

from typing import Any

import chess

from .course_gamebook import capture
from .course_guidance import attribution
from .course_pgn import chapter as pgn_chapter
from .fact_fingerprint import canonical, digest
from .related_capture import VERSION
from .related_transfer_admission import admit
from .unified_sources import resolve_source


def chapter(db, subject, selected, item, assessment):
    reference = digest(canonical([selected[4], item["type"], item["version"], item["key"]]))
    source_type, version, key, binding, lines = admit(
        selected, reference, VERSION, "material_capture"
    )
    binding["assessment"] = assessment
    snapshot: dict[str, Any] = resolve_source(db, source_type, version, key, subject=subject)
    if lines is not None:
        snapshot = {**snapshot, "lines": lines}
    snapshot = {
        **snapshot,
        "objective": "capture_named_target",
        "provenance": {**snapshot["provenance"], "objective_target": assessment["target"]},
    }
    interactive = capture(snapshot) is not None
    board = chess.Board(snapshot["prompt_fen"])
    square = chess.parse_square(binding["assessment"]["target"])
    piece = board.piece_at(square)
    if piece is None:
        raise ValueError("capture target unavailable")
    color = snapshot["learner_color"].capitalize()
    goal = f"Capture the {chess.piece_name(piece.piece_type)} on {chess.square_name(square)}."
    note = f"{color} to move. {goal} {attribution(db, 'corpus', version, snapshot)}"
    instruction = (
        "Use Preview to try the prepared line; another sound move may be rejected."
        if interactive
        else "This is an ungraded recorded line. Use the move controls to reveal it."
    )
    guidance = f"{note} {instruction} Use the coach practice link to check and record your answer."
    source = {"type": "corpus", "version": version, "key": key, "binding": binding}
    result = pgn_chapter(
        "Practice a related capture",
        note,
        snapshot,
        source,
        gamebook=interactive,
        guidance=guidance,
    )
    return result
