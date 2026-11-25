"""Enumerate current and legacy comparison attempts for one choice."""

from .opening_queue_artifact import path as result_path
from .opening_queue_binding import identity, legacy_config
from .opening_queue_failure import path as failure_path


def paths(directory, database, source, config):
    values = [config, legacy_config(config)]
    selected = [
        {"id": identity(database, source, value), "attempt": attempt}
        for value in values
        if value is not None
        for attempt in range(3)
    ]
    return [path(directory, item) for item in selected for path in (result_path, failure_path)]
