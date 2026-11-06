"""Show current private comparison state without starting engine work."""

from .opening_queue_binding import request, snapshot
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
    for choice in items:
        budget.check()
        binding = {**source, "alternative": choice["uci"], "child": choice["child"]}
        current = request(database, binding, config)
        value = state(directory, current, slot, owned["board"])
        output[choice["uci"]] = {**value, "_identity": current["id"]} if with_identity else value
    budget.check()
    return output
