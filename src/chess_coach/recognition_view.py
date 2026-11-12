"""Build a neutral prompt or the frozen supported result."""

from .recognition_current import source
from .recognition_messages import unavailable
from .recognition_novelty import novel
from .recognition_store import row


def view(db, subject, attempt):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    saved = row(db, subject, attempt)
    try:
        board, proof = source(db, saved)
        if saved["action"] is None:
            novel(db, saved)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("recognition sources changed")
    except (ValueError, TypeError, KeyError) as error:
        return {"status": "unavailable", "reason": unavailable(error)}
    result = {"status": "active", "fen": board.fen(), "color": saved["learner_color"]}
    if saved["action"] is None:
        return result
    result.update(status="complete", assisted=bool(saved["assisted"]), answer=saved["answer"])
    kind = proof["kind"]
    result["outcome"] = (
        "ungraded"
        if saved["answer"] in (None, "uncertain")
        else "correct"
        if saved["answer"] == kind
        else "incorrect"
    )
    if kind == "mate":
        result["explanation"] = {"kind": kind, "san": proof["mate"]["san"]}
    else:
        capture = proof["proof"]
        result["explanation"] = {
            "kind": kind,
            "san": capture["proof"]["san"],
            "target": capture["target"],
            "gain": capture["proof"]["proven_gain_floor"],
        }
    return result
