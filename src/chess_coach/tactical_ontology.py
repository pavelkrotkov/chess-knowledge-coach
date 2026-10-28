"""Seed a complete, explicitly versioned tactical ontology without rewriting history."""

from __future__ import annotations

from .db import Database
from .ontology import EDGES, SEED

DESCRIPTION = "Execute an immediate legal checkmate when one is available"


def seed_tactical_ontology(db: Database, *, version: str) -> None:
    if not version:
        raise ValueError("ontology version is required")
    if db.connection.in_transaction:
        raise RuntimeError("cannot seed ontology during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        seed_tactical_ontology_in_transaction(db, version=version)
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise


def seed_tactical_ontology_in_transaction(db: Database, *, version: str) -> None:
    if not version:
        raise ValueError("ontology version is required")
    if not db.connection.in_transaction:
        raise RuntimeError("ontology seeding requires a transaction")
    _seed(db, version)


def _seed(db: Database, version: str) -> None:
    skills = {**SEED, "mate_in_one": DESCRIPTION}
    edges = [*EDGES, ("tactics", "mate_in_one", "contains")]
    stored_skills, stored_edges = _snapshot(db, version)
    expected_edges = {(parent, version, child, version, kind) for parent, child, kind in edges}
    if stored_skills or stored_edges:
        if stored_skills != skills or stored_edges != expected_edges:
            raise ValueError("ontology version already has different contents")
        return
    db.connection.executemany(
        "INSERT INTO skills(skill, description, ontology_version) VALUES (?, ?, ?)",
        [(skill, description, version) for skill, description in skills.items()],
    )
    db.connection.executemany(
        """INSERT INTO skill_edges
        (parent_skill, parent_version, child_skill, child_version, edge_type, ontology_version)
        VALUES (?, ?, ?, ?, ?, ?)""",
        [(parent, version, child, version, kind, version) for parent, child, kind in edges],
    )


def _snapshot(db: Database, version: str):
    stored_skills = {
        row["skill"]: row["description"]
        for row in db.connection.execute(
            "SELECT skill, description FROM skills WHERE ontology_version = ?", (version,)
        )
    }
    stored_edges = {
        tuple(row)
        for row in db.connection.execute(
            """SELECT parent_skill, parent_version, child_skill, child_version, edge_type
            FROM skill_edges WHERE ontology_version = ?""",
            (version,),
        )
    }
    return stored_skills, stored_edges
