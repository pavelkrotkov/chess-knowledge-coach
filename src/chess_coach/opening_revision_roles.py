"""Present a selected opening revision as distinct teaching roles."""

import io

import chess.pgn

from .course_pgn import chapter
from .fact_fingerprint import canonical, digest
from .opening_revision_course import VERSION as LEGACY_VERSION

VERSION = "opening-revision-course-v3"


def explanation(decision, choice, experiment):
    color = decision["color"]
    note = (
        f"You play {color.capitalize()}. In your game you played {decision['played']}; "
        f"this revision compares {choice['san']}. At depth {experiment['depth']}, "
        f"the played line scored {experiment['played']['score']} cp and the alternative "
        f"{experiment['alternative']['score']} cp from your perspective. "
        "These are bounded estimates for two moves, not proof of overall soundness. "
        "Continue to your worked comparison. If a public continuation is provided, "
        "use it as ungraded rehearsal."
    )
    snapshot = {
        "prompt_fen": decision["fen"],
        "learner_color": color,
        "lines": [experiment["played"]["uci"].split()[0]],
    }
    result = chapter("Opening revision explanation", note, snapshot, {}, guidance=note)
    return {"kind": "explanation", "title": "Why study this position", "pgn": result["pgn"]}


def version(source_version, chapters):
    payload = {"schema": VERSION, "course": source_version, "chapters": chapters}
    return digest(canonical(payload))


def three_roles(original):
    if original["schema"] != LEGACY_VERSION:
        raise ValueError("opening preview version differs")
    chapters = [explanation(original["decision"], original["choice"], original["experiment"])]
    chapters.extend(original["chapters"])
    if original["public_status"] == "available":
        public = chapters[-1]
        game = chess.pgn.read_game(io.StringIO(public["pgn"]))
        if game is None or game.errors:
            raise ValueError("opening continuation differs")
        game.comment += (
            f" You play {original['decision']['color'].capitalize()}. "
            "This recorded continuation is ungraded; other legal moves are not assessed. "
            "Study moves do not update your coach practice record."
        )
        chapters[-1] = {**public, "pgn": str(game)}
    return {
        **original,
        "schema": VERSION,
        "version": version(original["version"], chapters),
        "source_version": original["version"],
        "chapters": chapters,
    }


def preview(db, root, learner, game, position, move, *, deadline=None, with_identity=False):
    from .opening_revision_course import preview as legacy

    return three_roles(
        legacy(
            db, root, learner, game, position, move, deadline=deadline, with_identity=with_identity
        )
    )
