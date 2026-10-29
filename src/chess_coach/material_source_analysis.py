"""Choose owned deep lines or the current cheap checkpoint without mixing roles."""

from .material_lines import continuation


def current_lines(db, analysis, cheap_id, board):
    deep = analysis.get("deep")
    if deep and deep.get("result") and _usable(deep, board, analysis["played_move"]):
        result = deep["result"]
        best = result["best"] if deep["status"] == "complete" else None
        return best, result["played"], _provenance(db, deep, cheap_id)
    return analysis["best"], analysis["played"], {"kind": "cheap", "run_id": cheap_id}


def _usable(deep, board, played):
    if deep["status"] == "complete":
        return True
    if deep["status"] != "insufficient":
        return False
    return continuation(board, deep["result"]["played"], played, allow_checks=True) is not None


def _provenance(db, deep, cheap_id):
    row = db.connection.execute(
        "SELECT j.status AS job_status,a.status AS attempt_status FROM deep_analysis_jobs j JOIN deep_analysis_attempts a ON a.job_id=j.id WHERE j.id=? AND a.attempt_number=?",
        (deep["job_id"], deep["attempt_number"]),
    ).fetchone()
    if row is None:
        raise ValueError("current deep provenance unavailable")
    return {
        "kind": "deep",
        "run_id": deep["result"]["run_id"],
        "selection_id": deep["selection_id"],
        "job_id": deep["job_id"],
        "attempt_number": deep["attempt_number"],
        "cheap_run_id": cheap_id,
        "job_status": row["job_status"],
        "attempt_status": row["attempt_status"],
        "result_status": deep["status"],
        "qualified_roles": ["best", "played"] if deep["status"] == "complete" else ["played"],
    }
