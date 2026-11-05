"""Show the latest locally verified tactical Study without changing the old link."""

from itertools import islice

from .tactical_study_intents import MAX_INTENTS
from .tactical_study_path import planning
from .tactical_study_receipt import verified


def status(root, subject):
    try:
        directory, expected = planning(root, subject)
        paths = list(islice(directory.glob("tactical-study-*-intent.json"), MAX_INTENTS + 1))
        if len(paths) > MAX_INTENTS:
            return None
        values = []
        for path in paths:
            try:
                value = verified(path, expected)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue
            if value:
                values.append(value)
        return max(values, key=lambda value: value[0])[1] if values else None
    except (OSError, TypeError, ValueError):
        return None
