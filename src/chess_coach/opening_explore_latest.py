"""Use the private comparison slot only as an untrusted nomination."""

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_validate import valid
from .recurrence_cursor import _valid_id


def hint(db, root, learner):
    if not root:
        return None
    try:
        directory, database = location(db, root, learner)
        slot = read(directory / "opening-comparison-slot.json")
        if not valid(slot, database):
            return None
        return slot if _usable(slot["source"], learner) else None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _usable(source, learner):
    alternative = source.get("alternative")
    return (
        source.get("learner_key") == learner_key(learner)
        and _valid_id(source.get("game_id"))
        and _valid_id(source.get("position_id"))
        and isinstance(alternative, str)
        and len(alternative) <= 5
    )
