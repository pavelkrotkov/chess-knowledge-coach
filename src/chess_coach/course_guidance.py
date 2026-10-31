"""Describe admitted objectives and explain how to use each chapter."""

from .course_gamebook import capture, mate


def objective(note, snapshot, kind):
    target = capture(snapshot) if kind == "capture" else None
    interactive = bool(target) if kind == "capture" else kind == "mate" and mate(snapshot)
    if target:
        goal = f"Capture the {target} and win material."
    elif interactive:
        goal = "Checkmate in one move."
    elif kind == "protection":
        goal = "Replay the recorded defense; other defenses may also work."
    elif kind == "capture":
        goal = "Follow the recorded material-gain line."
    else:
        goal = "Study the recorded mating idea."
    return f"Goal: {goal} {note}".strip(), interactive


def prompt(note, color, gamebook):
    if gamebook:
        prefix = f"Interactive exercise. You play {color.capitalize()}."
        instruction = (
            "Select Preview below the board. Your move is checked automatically. "
            "A correct move shows Correct. Exercise complete. with Play again and Next chapter; "
            "a nonmatching move asks you to retry."
        )
    else:
        prefix = f"Worked example, ungraded. You follow {color.capitalize()}'s recorded line."
        instruction = (
            "Use the move controls to step through the recorded line; other moves are not "
            "judged here. Preview is used for the interactive chapters."
        )
    return f"{prefix} {note} {instruction}"


def chapter_title(title, color, gamebook):
    label = f"Play {color.capitalize()} (Preview)" if gamebook else f"Example {color.capitalize()}"
    return f"{label}: {title}"


def attribution(db, source_type, version, snapshot):
    if source_type == "public":
        provenance = snapshot["provenance"]
        return "Source: {}. License: {}.".format(provenance["attribution"], provenance["license"])
    row = db.connection.execute(
        "SELECT source FROM puzzle_corpora WHERE version=?", (version,)
    ).fetchone()
    if row and row[0].startswith("https://database.lichess.org/"):
        return "Source: Lichess open puzzle database, CC0."
    return "Source: practice puzzle library."
