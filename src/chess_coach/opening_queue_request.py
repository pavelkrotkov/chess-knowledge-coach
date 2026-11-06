"""Admit one current catalog comparison into the private single slot."""

import os

from .opening_queue_binding import request, snapshot
from .opening_queue_choice import choose
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_validate import valid
from .opening_queue_write import staged, sync


def admit(db, root, learner, game, position, alternative, *, retry=False):
    directory, database = location(db, root, learner)
    budget, source, config, _ = snapshot(db, database, learner, game, position, alternative)
    selected = request(database, source, config)
    with lock(directory):
        slot_path = directory / "opening-comparison-slot.json"
        old = read(slot_path)
        if old is not None and not valid(old, old.get("database")):
            raise ValueError("comparison slot unavailable")
        selected = choose(directory, selected, old, retry)
        with staged(slot_path, selected) as temporary, budget.publication():
            os.replace(temporary, slot_path)
        sync(directory)
    return selected
