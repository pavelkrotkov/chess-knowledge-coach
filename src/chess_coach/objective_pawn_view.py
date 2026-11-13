"""Display validated pawn-result feedback and any proved training reply."""

from .objective_pawn_continue import latest
from .objective_pawn_feedback import checked
from .objective_pawn_resume import resume


def display(db, session, result):
    item = latest(db, session)
    if item is None:
        return
    request, proof = item
    if proof.get("status") not in {"correct", "incorrect"}:
        return
    try:
        board, move, feedback = checked(db, session, request, proof)
        result["pawn_feedback"] = feedback
        if proof.get("continuation", {}).get("status") == "available":
            resumed = resume(db, session, request, proof, prepared=(board, move))
            result["fen"] = resumed["board"].fen()
            result["status"] = "active"
            result["pawn_continuation"] = True
        elif proof["status"] == "correct":
            result["pawn_continuation_unavailable"] = True
    except (ValueError, KeyError, TypeError, IndexError):
        result.pop("pawn_feedback", None)
        result["verification"] = {"status": "unresolved", "reason": "source_unavailable"}
