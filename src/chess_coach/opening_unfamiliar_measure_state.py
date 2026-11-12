"""Describe one current, source-bound opening comparison."""

import chess

from .opening_experiment import assess
from .opening_queue_view import statuses
from .tactical_course_deadline import PreviewDeadline


def _line(board, line):
    replay, san = board.copy(), []
    for uci in line["pv"].split()[:4]:
        move = replay.parse_uci(uci)
        san.append(replay.san(move))
        replay.push(move)
    return {"score": line["score_value"], "depth": line["depth"], "san": san}


def state(db, root, learner, decision, choice, budget):
    narrow = {**decision, "catalog": {**decision["catalog"], "items": [choice]}}
    state = statuses(db, root, learner, narrow, deadline=budget.expires).get(choice["uci"], {})
    result = {"status": state.get("status", "unavailable"), "decision": decision, "choice": choice}
    if result["status"] == "complete":
        _, reason = assess(decision, choice, state)
        board = chess.Board(decision["fen"])
        lines = {line["root_move"]: _line(board, line) for line in state["lines"]}
        result.update(
            reason=reason, played=lines[decision["played_uci"]], other=lines[choice["uci"]]
        )
    budget.check()
    return result


def checked(db, root, learner, decision, choice, budget):
    try:
        return state(db, root, learner, decision, choice, budget)
    except (Exception, PreviewDeadline):
        return {"status": "unavailable"}
