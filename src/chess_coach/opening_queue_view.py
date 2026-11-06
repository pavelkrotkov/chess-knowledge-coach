"""Show current private comparison state without starting engine work."""

from .opening_queue_binding import request, snapshot
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_validate import valid
from .opening_queue_view_state import state


def statuses(db, root, learner, decision):
    directory, database = location(db, root, learner)
    items = decision["catalog"]["items"]
    if not items:
        return {}
    budget, source, config, owned = snapshot(
        db, database, learner, decision["game_id"], decision["position_id"], items[0]["uci"]
    )
    slot = read(directory / "opening-comparison-slot.json")
    if slot is not None and not valid(slot, slot.get("database")):
        raise ValueError("comparison slot unavailable")
    output = {}
    for choice in items:
        binding = {**source, "alternative": choice["uci"], "child": choice["child"]}
        current = request(database, binding, config)
        output[choice["uci"]] = state(directory, current, slot, owned["board"])
    budget.check()
    return output
