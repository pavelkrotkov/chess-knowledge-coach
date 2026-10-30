"""Summarize new native search work without summing shared MultiPV lines."""

import json


def attempt_count(db, request_id):
    return db.connection.execute(
        "SELECT COUNT(*) FROM purpose_analysis_attempts WHERE request_id=?", (request_id,)
    ).fetchone()[0]


def new_work(db, request_id, before):
    rows = db.connection.execute(
        """SELECT result_json FROM purpose_analysis_attempts WHERE request_id=?
        ORDER BY attempt_number LIMIT -1 OFFSET ?""",
        (request_id, before),
    ).fetchall()
    if not rows:
        return {"searches": [], "unknown": False}
    searches = []
    unknown = False
    for row in rows:
        result = json.loads(row["result_json"])
        found = [result.get("scout"), result.get("final")]
        found = [item for item in found if isinstance(item, dict)]
        if not found:
            unknown = True
        for item in found:
            work = item.get("work", {})
            searches.append(
                {
                    "requested_nodes": work.get("requested_nodes"),
                    "actual_nodes": work.get("nodes"),
                    "overshoot": work.get("node_limit_exceeded"),
                }
            )
            unknown |= work.get("nodes") is None or work.get("requested_nodes") is None
    return {"searches": searches, "unknown": unknown}
