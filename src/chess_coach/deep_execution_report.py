"""Summarize current deep-job progress without exposing source identity."""


def execution_report(db, selection_id, processed):
    rows = db.connection.execute(
        """SELECT j.status,COUNT(*) AS n FROM deep_analysis_current c
        JOIN deep_analysis_jobs j ON j.id=c.job_id WHERE c.selection_id=? GROUP BY j.status""",
        (selection_id,),
    ).fetchall()
    counts = {row["status"]: row["n"] for row in rows}
    partial = any(status != "complete" for status in counts)
    status = "no_jobs" if not counts else "partial" if partial else "complete"
    return {
        "selection_id": selection_id,
        "status": status,
        "counts": counts,
        "processed": processed,
    }
