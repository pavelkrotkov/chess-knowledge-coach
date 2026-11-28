"""Compose a source-qualified protection lesson with explicit teaching roles."""

import chess

from .course_pgn import chapter
from .tactical_course_display import _note


def explanation(owned):
    snapshot = owned["source_snapshot"]
    provenance = snapshot["provenance"]
    if snapshot["objective"] != "protect_threatened_piece" or provenance["gain_threshold"] != 3:
        raise ValueError("protection objective unavailable")
    board = chess.Board(snapshot["prompt_fen"])
    target = chess.parse_square(provenance["objective_target"])
    piece = board.piece_at(target)
    move = board.parse_uci(snapshot["lines"][0])
    if not piece or piece.color != board.turn or move not in board.legal_moves:
        raise ValueError("protection source changed")
    prefix = f"Worked example, ungraded. {snapshot['learner_color'].capitalize()} to move. "
    note = _note(owned, board).removeprefix(prefix)
    guidance = (
        f"{snapshot['learner_color'].capitalize()} to move. Your "
        f"{chess.piece_name(piece.piece_type)} on {chess.square_name(target)} is threatened. "
        f"For the shown defense {board.san(move)}, the bounded check found no profitable "
        "immediate capture of that piece; later risks remain ungraded. "
        f"{note} Follow the next chapter for the worked example."
    )
    return {
        **chapter(
            "Understand the threatened piece", note, snapshot, owned["source"], guidance=guidance
        ),
        "role": "explanation",
    }


def worked(note, snapshot, source):
    note = note.replace(
        "This is a recorded line, not a mastery result.",
        "The shown defense was checked separately from the played move; this is not a mastery result.",
    )
    guidance = f"Worked example, ungraded. {snapshot['learner_color'].capitalize()} to move. {note}"
    return chapter("Your recurring pattern", note, snapshot, source, guidance=guidance)


def rehearsal(practice):
    snapshot = practice["source_snapshot"]
    board = chess.Board(snapshot["prompt_fen"])
    note = _note(practice, board)
    first = board.san(board.parse_uci(snapshot["lines"][0].split()[0]))
    note = note.replace(
        f"Follow the supplied defensive line from {first};", "Follow the supplied defensive line;"
    )
    guidance = (
        f"Ungraded rehearsal. {snapshot['learner_color'].capitalize()} to move. "
        f"Try a defense, then reveal the supplied line. {note} "
        "Other defenses may also work; this Study does not record practice results."
    )
    return {
        **chapter("Practice a defense", note, snapshot, practice["source"], guidance=guidance),
        "role": "practice",
    }


def compose(owned, practice):
    chapters = [explanation(owned), {**owned, "role": "worked"}]
    if practice is not None:
        chapters.append(rehearsal(practice))
    return chapters
