"""Display a proved promotion or its remaining legal promotion turn."""

from .objective_promotion_continue import continuation


def display(db, row, result):
    resumed = continuation(db, row)
    if resumed:
        result["fen"] = resumed["board"].fen()
        result["status"] = "objective_verified" if resumed["complete"] else "active"
        result["promotion_continuation"] = not resumed["complete"]
