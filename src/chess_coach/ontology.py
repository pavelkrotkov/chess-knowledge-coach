"""Versioned skill ontology and detector-fact mapper."""

from __future__ import annotations

from typing import Any

from .db import Database
from .ontology_mapping import map_facts

SEED = {
    "tactics": "Pattern-based tactical opportunities",
    "fork": "Attack two or more valuable targets",
    "hanging_piece": "Identify undefended enemy material",
    "absolute_pin": "Identify a piece pinned to its king",
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
            """INSERT OR REPLACE INTO skill_edges
            (parent_skill, parent_version, child_skill, child_version, edge_type, ontology_version)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (parent, version, child, version, edge_type, version),
        )
    db.connection.commit()
    return len(SEED)


def skill_descendants(db: Database, skill: str, *, version: str | None = None) -> set[str]:
    version = (
        version
        or db.connection.execute(
            "SELECT ontology_version FROM skills WHERE skill = ? ORDER BY ontology_version DESC LIMIT 1",
            (skill,),
        ).fetchone()[0]
    )
    query = """WITH RECURSIVE descendants(skill, version) AS (
        SELECT child_skill, child_version FROM skill_edges
        WHERE parent_skill = ? AND parent_version = ? AND ontology_version = ? AND edge_type = 'contains'
        UNION
        SELECT edge.child_skill, edge.child_version FROM skill_edges edge
        JOIN descendants d ON edge.parent_skill = d.skill AND edge.parent_version = d.version
        WHERE edge.ontology_version = ? AND edge.edge_type = 'contains'
    ) SELECT skill FROM descendants"""
    return {row[0] for row in db.connection.execute(query, (skill, version, version, version))}


def map_detector_facts(
    db: Database,
    mapper_version: str,
    *,
    detector_version: str | None = None,
) -> list[dict[str, Any]]:
    return map_facts(db, mapper_version, detector_version=detector_version)
