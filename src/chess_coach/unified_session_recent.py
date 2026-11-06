"""Present bounded recent attempts without implying unsupported checks."""

from .unified_public_outcome import outcome as public_outcome


def recent(db, subject):
    rows = db.connection.execute(
        """SELECT attempt_id,source_type,source_version,source_key,status,objective,current_fen,provenance_json
        FROM unified_sessions WHERE subject=? ORDER BY started_at DESC,attempt_id LIMIT 20""",
        (subject,),
    ).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        if item["source_type"] == "own-game" or item["status"] in {"active", "needs_verification"}:
            item.pop("source_key")
        public = public_outcome(item)
        if public is not None:
            item["status"] = public
        for field in ("objective", "current_fen", "provenance_json"):
            item.pop(field)
    return result
