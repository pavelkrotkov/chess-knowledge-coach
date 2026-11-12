"""Bounded private artifact hints, never a substitute for current source proof."""

import os
import re

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_unfamiliar_hint_match import matching

MAX_ENTRIES = 4096
MAX_ARTIFACTS = 128
NAME = re.compile(r"opening-comparison-([0-9a-f]{64})-([0-2])\.json\Z")


def hints(db, root, learner, parent, item, budget):
    directory, database = location(db, root, learner)
    result, entries, artifacts = set(), 0, 0
    with os.scandir(directory) as scan:
        for entry in scan:
            budget.check()
            entries += 1
            if entries > MAX_ENTRIES:
                return set()
            match = NAME.fullmatch(entry.name)
            if not match:
                continue
            artifacts += 1
            if artifacts > MAX_ARTIFACTS:
                return set()
            try:
                game = matching(
                    read(directory / entry.name), match, database, learner, parent, item
                )
                if game is not None:
                    result.add(game)
            except (OSError, ValueError, TypeError, KeyError):
                continue
    return result
