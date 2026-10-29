"""Check the active source link matches the reviewed evidence context."""


def valid_link(db, evidence, fact):
    row = db.connection.execute(
        """SELECT COUNT(*) FROM evidence_fact_links l
        JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
        WHERE l.evidence_id=? AND l.fact_id=? AND l.active=1 AND l.subject=?
        AND l.skill=? AND l.operation=? AND f.position_id=? AND d.position_id=?""",
        (
            evidence["id"],
            fact["id"],
            evidence["subject"],
            evidence["skill"],
            evidence["operation"],
            evidence["position_id"],
            evidence["position_id"],
        ),
    ).fetchone()
    return len(evidence["facts"]) == 1 and row[0] == 1
