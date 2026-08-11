"""Versioned skill ontology and detector-fact mapper."""

from __future__ import annotations

import json
from typing import Any

from .db import Database

SEED = {
    "tactics": "Pattern-based tactical opportunities",
    "fork": "Attack two or more valuable targets",
    "hanging_piece": "Identify undefended enemy material",
    "absolute_pin": "Identify a piece pinned to its king",
    "execute": "Carry out a known tactical operation",
}
EDGES = [
    ("tactics", "fork", "contains"),
    ("tactics", "hanging_piece", "contains"),
    ("tactics", "absolute_pin", "contains"),
]
FACT_OPERATIONS = {"fork": "execute", "hanging_piece": "prevent", "absolute_pin": "recognize"}


def seed_ontology(db: Database, version: str) -> int:
    for skill, description in SEED.items():
        db.connection.execute(
            "INSERT OR REPLACE INTO skills(skill, description, ontology_version) VALUES (?, ?, ?)",
            (skill, description, version),
        )
    for parent, child, edge_type in EDGES:
        db.connection.execute(
            "INSERT OR REPLACE INTO skill_edges(parent_skill, child_skill, edge_type, ontology_version) VALUES (?, ?, ?, ?)",
            (parent, child, edge_type, version),
        )
    db.connection.commit()
    return len(SEED)


def skill_descendants(db: Database, skill: str, *, version: str | None = None) -> set[str]:
    if version is None:
        query = """WITH RECURSIVE descendants(skill) AS (
            SELECT child_skill FROM skill_edges WHERE parent_skill = ?
            UNION
            SELECT edge.child_skill FROM skill_edges edge JOIN descendants d ON edge.parent_skill = d.skill
        ) SELECT skill FROM descendants"""
        params: list[Any] = [skill]
    else:
        query = """WITH RECURSIVE descendants(skill) AS (
            SELECT child_skill FROM skill_edges WHERE ontology_version = ? AND parent_skill = ?
            UNION
            SELECT edge.child_skill FROM skill_edges edge JOIN descendants d ON edge.parent_skill = d.skill
            WHERE edge.ontology_version = ?
        ) SELECT skill FROM descendants"""
        params = [version, skill, version]
    return {row[0] for row in db.connection.execute(query, params)}


def map_detector_facts(db: Database, mapper_version: str) -> list[dict[str, Any]]:
    rows = db.connection.execute(
        "SELECT id, position_id, fact_type, payload_json, detector_version FROM detector_facts ORDER BY id"
    ).fetchall()
    result = []
    for row in rows:
        skill = row["fact_type"]
        if skill not in FACT_OPERATIONS:
            continue
        operation = FACT_OPERATIONS[skill]
        payload = json.loads(row["payload_json"])
        db.connection.execute(
            """INSERT INTO evidence_mappings
            (position_id, skill, operation, outcome, confidence, source_facts_json, mapper_version)
            VALUES (?, ?, ?, 'ambiguous', ?, ?, ?)""",
            (row["position_id"], skill, operation, 1.0, json.dumps([payload]), mapper_version),
        )
        result.append(
            {
                "position_id": row["position_id"],
                "skill": skill,
                "operation": operation,
                "confidence": 1.0,
                "source_facts": [row["id"]],
                "detector_version": row["detector_version"],
                "mapper_version": mapper_version,
            }
        )
    db.connection.commit()
    return result
