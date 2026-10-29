"""Grade only answers supported by a bounded task proof."""

import chess


def response(task, kind, answer, elapsed, assisted):
    if kind == "hint":
        return {
            "kind": kind,
            "message": "This task is based on a position and pattern already shown in the lesson.",
        }
    if kind == "reveal":
        return {"kind": kind, "message": "Accepted answers: " + ", ".join(task["accepted"])}
    normalized = _normalize(task, answer)
    matched = normalized in task["accepted"]
    return {
        "kind": kind,
        "answer": answer,
        "elapsed_seconds": elapsed,
        "elapsed_basis": "wall time since task start",
        "assisted": assisted,
        "outcome": "supported" if matched else "ungraded",
        "operation": task["operation"],
        "evidence": _evidence(task, matched, assisted),
        "message": _feedback(matched, assisted),
    }


def _normalize(task, answer):
    value = answer.strip()
    if task["operation"] == "recognize":
        return value.lower()
    try:
        board = chess.Board(task["fen"])
        return board.san(board.parse_san(value))
    except (ValueError, TypeError):
        return ""


def _feedback(matched, assisted):
    if not matched:
        return "This answer is ungraded; another answer may be valid outside the bounded proof. It does not establish a blind spot."
    if assisted:
        return "This matches the cited proof after assistance. It does not establish unaided recognition, calculation, or mastery."
    return "This matches the cited proof in a familiar, cued task. One response cannot establish why a game move happened or prove mastery."


def _evidence(task, matched, assisted):
    if not matched or assisted:
        return None
    return {
        "operation": task["operation"],
        "outcome": "success",
        "policy": task["version"],
        "qualification": task["familiarity"],
    }
