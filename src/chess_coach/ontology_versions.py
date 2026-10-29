"""Guard previously stored ontology versions against replacement."""

from .db import Database


def existing_version(db: Database, version: str, skills: dict, relations: list) -> bool:
    existing = {
        row["skill"]: row["description"]
        for row in db.connection.execute(
            "SELECT skill, description FROM skills WHERE ontology_version = ?", (version,)
        )
    }
    edges = {
        tuple(row)
        for row in db.connection.execute(
            "SELECT parent_skill, parent_version, child_skill, child_version, edge_type FROM skill_edges WHERE ontology_version = ?",
            (version,),
        )
    }
    if not existing and not edges:
        return False
    expected = {(a, version, b, version, kind) for a, b, kind in relations}
    if existing != skills or edges != expected:
        raise ValueError("ontology version already has different contents")
    return True
