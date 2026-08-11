from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, cast

from .db import Database


def record_evidence(
    db: Database,
    *,
    skill: str,
    operation: str,
    outcome: str,
    confidence: float,
    position_id: int | None = None,
    source_facts: list[str] | None = None,
    mapper_version: str = "0.1.0",
    context: dict[str, Any] | None = None,
) -> int:
    if outcome not in {"success", "failure", "ambiguous"}:
        raise ValueError("outcome must be success, failure, or ambiguous")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    cursor = db.connection.execute(
        """INSERT INTO evidence_mappings
        (position_id, skill, operation, outcome, confidence, source_facts_json, mapper_version, context_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            position_id,
            skill,
            operation,
            outcome,
            confidence,
            json.dumps(source_facts or []),
            mapper_version,
            json.dumps(context or {}, sort_keys=True),
        ),
    )
    db.connection.commit()
    return cast(int, cursor.lastrowid)


def validate_evidence(db: Database, evidence_id: int) -> None:
    cursor = db.connection.execute(
        "UPDATE evidence_mappings SET human_validated = 1 WHERE id = ?", (evidence_id,)
    )
    if cursor.rowcount != 1:
        raise ValueError(f"unknown evidence mapping: {evidence_id}")
    db.connection.commit()


def evidence_report(db: Database) -> list[dict[str, Any]]:
    rows = db.connection.execute(
        """SELECT skill, operation, outcome, COUNT(*) AS count
        FROM evidence_mappings GROUP BY skill, operation, outcome
        ORDER BY skill, operation, outcome"""
    ).fetchall()
    report: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for row in rows:
        key = (row["skill"], row["operation"])
        report[key].update({"skill": row["skill"], "operation": row["operation"]})
        report[key][row["outcome"]] = row["count"]
    return [
        {
            "skill": skill,
            "operation": operation,
            "opportunities": item.get("success", 0)
            + item.get("failure", 0)
            + item.get("ambiguous", 0),
            "success": item.get("success", 0),
            "failure": item.get("failure", 0),
            "ambiguous": item.get("ambiguous", 0),
        }
        for (skill, operation), item in sorted(report.items())
    ]
