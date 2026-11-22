"""Show current private comparison state without starting engine work."""

from .opening_queue_binding import legacy_config, request, snapshot
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_validate import valid
from .opening_queue_view_state import state


def statuses(db, root, learner, decision, *, deadline=None, with_identity=False):
    directory, database = location(db, root, learner)
    items = decision["catalog"]["items"]
    if not items:
        return {}
    budget, source, config, owned = snapshot(
        db,
        database,
        learner,
        decision["game_id"],
        decision["position_id"],
        items[0]["uci"],
        deadline=deadline,
    )
    slot = read(directory / "opening-comparison-slot.json")
    if slot is not None and not valid(slot, slot.get("database")):
        raise ValueError("comparison slot unavailable")
    output = {}
    prior_config = legacy_config(config)
    for choice in items:
        budget.check()
        binding = {**source, "alternative": choice["uci"], "child": choice["child"]}
        current = request(database, binding, config)
        legacy = request(database, binding, prior_config) if prior_config else None
        value = _state(directory, current, slot, owned["board"], legacy)
        identity = value.pop("_identity", current["id"])
        output[choice["uci"]] = {**value, "_identity": identity} if with_identity else value
    budget.check()
    return output


def _state(directory, current, slot, board, legacy):
    # Retain historical work without treating a two-root result as a reference.
    value = state(directory, current, slot, board)
    if legacy is None or value["status"] not in ("none", "stale"):
        return value
    earlier = state(directory, legacy, slot, board)
    if earlier["status"] in ("none", "stale"):
        return value
    return {**earlier, "historical": True, "_identity": legacy["id"]}
