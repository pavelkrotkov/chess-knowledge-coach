"""Build a private worked-example PGN for one qualified opening experiment."""

from .course_pgn import chapter


def pgn(decision, choice, experiment):
    snapshot = {
        "prompt_fen": decision["fen"],
        "learner_color": decision["color"],
        "lines": [experiment["played"]["uci"], experiment["alternative"]["uci"]],
    }
    note = (
        f"Played move: {decision['played']}; alternative: {choice['san']}. "
        f"Two-root estimates: played {experiment['played']['score']} cp, "
        f"alternative {experiment['alternative']['score']} cp, depth {experiment['depth']}. "
        "Replay the played branch. From the starting position, choose the alternative and "
        f"after {experiment['alternative']['san'][1]}, find your continuation before revealing the worked line. "
        "These estimates cover the two shown roots at the recorded depth. "
        "Overall soundness and personal fit remain unknown."
    )
    return chapter("Opening experiment", note, snapshot, {}, guidance=note)["pgn"]
