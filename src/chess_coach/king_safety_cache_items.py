"""Reconstruct mapping output and verify its active fact link."""

import json


def _same_scope(evidence, row):
    return all(
        evidence[key] == row[key]
        for key in ("position_id", "subject", "operation", "mapper_version")
    )


def _valid_link(db, evidence, fact):
    links = db.connection.execute(
        "SELECT * FROM evidence_fact_links WHERE evidence_id=? AND active=1", (evidence["id"],)
    ).fetchall()
    if len(links) != 1 or links[0]["fact_id"] != fact["id"]:
        return False
    return not any(links[0][key] != evidence[key] for key in ("subject", "skill", "operation"))


def items(db, row, facts):
    rows = db.connection.execute(
        "SELECT * FROM evidence_mappings WHERE mapping_run_id=?", (row["id"],)
    ).fetchall()
    if len(rows) != len(facts):
        return None
    if not rows:
        return []
    evidence, fact = rows[0], facts[0]
    if not _same_scope(evidence, row) or json.loads(evidence["source_facts_json"]) != [fact["id"]]:
        return None
    if not _valid_link(db, evidence, fact):
        return None
    return [
        {
            "skill": evidence["skill"],
            "outcome": evidence["outcome"],
            "confidence": evidence["confidence"],
            "fact_ids": [fact["id"]],
            "context": json.loads(evidence["context_json"]),
            "observation_at": evidence["observation_at"],
        }
    ]
