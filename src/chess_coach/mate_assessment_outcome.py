"""Classify only fully validated short-mate assessment events."""


def outcome(row, feedback):
    if row["status"] == "active":
        return "incomplete"
    if row["status"] == "needs_verification":
        return "unresolved"
    if row["status"] == "objective_verified":
        return "verified"
    if row["status"] == "line_completed" and feedback == "incorrect":
        return "incorrect"
    raise ValueError("assessment outcome unavailable")
