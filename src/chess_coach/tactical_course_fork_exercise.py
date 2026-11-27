"""Render and rebind one qualified, concealed fork course exercise."""

import chess

from .course_guidance import attribution, challenge
from .course_pgn import chapter as pgn_chapter
from .fact_fingerprint import canonical, digest
from .fork_comparison_context import context
from .related_fork import VERSION
from .related_fork_assessment import certificate
from .related_fork_assessment_current import current
from .related_transfer_admission import admit
from .tactical_course_fork_provenance import require
from .unified_sources import resolve_source


def chapter(db, subject, selected, item, choice, saved, check):
    reference = digest(canonical([selected[4], item["type"], item["version"], item["key"]]))
    source_type, version, key, binding, lines = admit(selected, reference, VERSION, "fork")
    if saved is None:
        assessment = certificate(db, version, key, check=check)
        assessment["context"] = context(db, version, key)
    else:
        assessment = saved["binding"]["assessment"]
    binding["assessment"] = assessment
    snapshot = resolve_source(db, source_type, version, key, subject=subject)
    if lines is not None:
        snapshot = {**snapshot, "lines": lines}
    current(
        db,
        {"source_version": version, "source_key": key, "prompt_fen": snapshot["prompt_fen"]},
        binding,
        snapshot,
    )
    board = chess.Board(snapshot["prompt_fen"])
    piece = board.piece_at(chess.parse_square(assessment["attacker"]))
    if piece is None or piece.piece_type != chess.KNIGHT:
        raise ValueError("knight fork practice unavailable")
    color = snapshot["learner_color"].capitalize()
    note = f"{color} to move. Find a knight fork attacking the target on {assessment['anchor']}. {attribution(db, source_type, version, snapshot)}"
    guidance = (
        f"{note} This concealed Study line is ungraded; try a move, then use the move controls to reveal the line. "
        f"The local coach can check alternative-aware fork practice at {challenge(choice, protection=True)}, "
        "but may choose a different exercise. Study activity does not automatically record a coach answer."
    )
    source = {"type": source_type, "version": version, "key": key, "binding": binding}
    result = pgn_chapter(
        "Practice a related knight fork", note, snapshot, source, guidance=guidance
    )
    if saved is not None:
        require(db, subject, result)
    return result
