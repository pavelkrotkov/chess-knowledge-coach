"""Capture the exact verified original protection lineage and history."""

from .material_contract import VERSION as MAPPER_VERSION
from .material_policy import MAPPER
from .objective_protection_contract import VERSION
from .objective_protection_judge import VERSION as VERIFIER
from .purpose_source_binding import history_fingerprint, owned_game


def binding(db, learner, item, evidence, source):
    provenance = source["provenance"]
    if provenance["position_id"] != item["position_id"]:
        raise ValueError("protection position changed")
    game, color = owned_game(db, item["game_id"], learner)
    rows = db.connection.execute(
        "SELECT id,ply,fen,uci FROM positions WHERE game_id=? ORDER BY ply", (item["game_id"],)
    ).fetchall()
    return {
        "evidence_id": evidence,
        "source_contract": VERSION,
        "mapper": MAPPER,
        "mapper_version": MAPPER_VERSION,
        "verifier": VERIFIER,
        "history_fingerprint": history_fingerprint(game, color, rows),
        "provenance": provenance,
    }
