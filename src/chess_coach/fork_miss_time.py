"""Match known game time controls across the two samples."""

import re
from collections import Counter


def distribution(values):
    result = []
    for value in values:
        if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\+[0-9]+)?", value):
            return None
        base, _, increment = value.partition("+")
        try:
            if int(base) == 0 and (not increment or int(increment) == 0):
                return None
        except ValueError:
            return None
        result.append(value)
    return Counter(result)


def _values(db, games):
    for game in games:
        row = db.connection.execute(
            "SELECT time_control FROM games WHERE id=?", (game["id"],)
        ).fetchone()
        yield row[0] if row else None


def _times(db, games):
    return distribution(_values(db, games))
