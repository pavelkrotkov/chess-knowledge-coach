"""Attach only exact-exemplar scores and indexed public examples."""

import time

from .opening_queue_view import statuses
from .opening_reference_read import matches
from .tactical_course_deadline import PreviewDeadline


def enrich(db, root, learner, report):
    branch = report["branch"]
    if branch is None:
        return
    exemplar = branch["exemplar"]
    alternative = exemplar["catalog"]["items"][0]
    branch["alternative"] = alternative
    branch["references"] = matches(root, learner, branch["position"])
    branch["comparison"] = None
    if time.monotonic() + 5 < report["_deadline"]:
        branch["comparison"] = comparison(db, root, learner, exemplar, alternative)
    else:
        report["partial"] = True
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != report["_version"]:
        raise ValueError("opening sample changed")


def comparison(db, root, learner, exemplar, alternative):
    decision = {
        "game_id": exemplar["game_id"],
        "position_id": exemplar["position_id"],
        "catalog": {"items": [alternative]},
    }
    try:
        state = statuses(db, root, learner, decision).get(alternative["uci"], {})
    except (Exception, PreviewDeadline):
        return None
    if state.get("status") != "complete":
        return None
    lines = {line["root_move"]: line for line in state["lines"]}
    played, other = lines.get(exemplar["played_uci"]), lines.get(alternative["uci"])
    if played is None or other is None:
        return None
    return {
        "played": played["score_value"],
        "alternative": other["score_value"],
        "depth": played["depth"],
    }
