"""Display a separately proved pawn training reply when available."""

from .objective_pawn_continue import continuation


def display(db, row, result):
    resumed = continuation(db, row)
    if resumed:
        result["fen"] = resumed["board"].fen()
        result["status"] = "active"
        result["pawn_continuation"] = True
    elif result.get("verification", {}).get("status") == "correct":
        result["pawn_continuation_unavailable"] = True
