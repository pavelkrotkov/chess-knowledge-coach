"""Select one bounded, evidence-bearing protection candidate."""

from .learner_identity import normalize_identity
from .material_policy import MAPPER
from .style_protection_schedule_rotation import choose


def _evidence_positions(db, learner, candidates):
    ids = [item["position_id"] for item in candidates]
    if not ids:
        return set()
    placeholders = ",".join("?" for _ in ids)
    rows = db.connection.execute(
        f"""SELECT DISTINCT e.position_id FROM evidence_mappings e
        JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.position_id IN ({placeholders}) AND e.subject=? AND r.producer=?
        AND r.status='active' AND e.skill='hanging_piece' AND e.operation='prevent'""",
        (*ids, normalize_identity(learner), MAPPER),
    )
    return {row[0] for row in rows}


def select(db, learner, key, candidates, slots):
    available = _available(candidates, slots)
    positions = _evidence_positions(db, learner, available)
    return choose(db, key, [item for item in available if item["position_id"] in positions])


def _available(candidates, slots):
    existing = {item["game_id"]: item["position_id"] for _kind, item in slots if item}
    return [
        item
        for item in candidates
        if not item["in_check"]
        and (item["game_id"] not in existing or existing[item["game_id"]] == item["position_id"])
    ]
