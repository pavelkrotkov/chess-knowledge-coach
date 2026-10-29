"""Validate and persist an immutable version of the competency graph."""

from .competency_seed import EDGES, GRAPH_VERSION, SKILLS
from .competency_validation import validate_graph
from .db import Database
from .tactical_ontology import _snapshot


def seed_competency_graph(db: Database) -> int:
    """Seed a version once; never overwrite an existing version or caller transaction."""
    validate_graph(SKILLS, EDGES)
    if db.connection.in_transaction:
        raise RuntimeError("cannot seed competencies during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        _seed(db)
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
    return len(SKILLS)


def _seed(db: Database) -> None:
    stored_skills, stored_edges = _snapshot(db, GRAPH_VERSION)
    expected = {(a, GRAPH_VERSION, b, GRAPH_VERSION, kind) for a, b, kind in EDGES}
    if stored_skills or stored_edges:
        if stored_skills != SKILLS or stored_edges != expected:
            raise ValueError("competency graph version already has different contents")
        return
    db.connection.executemany(
        "INSERT INTO skills(skill, description, ontology_version) VALUES (?, ?, ?)",
        [(skill, desc, GRAPH_VERSION) for skill, desc in SKILLS.items()],
    )
    db.connection.executemany(
        "INSERT INTO skill_edges (parent_skill, parent_version, child_skill, child_version, edge_type, ontology_version) VALUES (?, ?, ?, ?, ?, ?)",
        [(a, GRAPH_VERSION, b, GRAPH_VERSION, kind, GRAPH_VERSION) for a, b, kind in EDGES],
    )
