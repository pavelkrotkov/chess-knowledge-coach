"""Resolve currentness and present selection items without source fingerprints."""

import json

from .deep_selection_source import source_snapshot


def selection_state(db, game_id, learner, current_id, run):
    if run["id"] != current_id:
        return "historical"
    try:
        source = source_snapshot(db, game_id, learner)
    except ValueError:
        return "stale"
    if (
        source["cheap_run_id"] != run["cheap_run_id"]
        or source["input_fingerprint"] != run["input_fingerprint"]
    ):
        return "stale"
    return "current"


def selection_items(db, selection_id, state):
    rows = db.connection.execute(
        """SELECT i.position_id,i.rank,i.allocation,i.reasons_json,p.ply,j.status AS job_status
        FROM deep_selection_items i JOIN positions p ON p.id=i.position_id
        LEFT JOIN deep_analysis_current c ON c.selection_id=i.selection_id AND c.position_id=i.position_id
        LEFT JOIN deep_analysis_jobs j ON j.id=c.job_id
        WHERE i.selection_id=? ORDER BY i.rank""",
        (selection_id,),
    ).fetchall()
    return [
        {
            "position_id": row["position_id"],
            "ply": row["ply"],
            "rank": row["rank"],
            "allocation": row["allocation"],
            "reasons": json.loads(row["reasons_json"]),
            "status": (row["job_status"] or "pending_deep")
            if state == "current"
            else "not_current",
        }
        for row in rows
    ]
