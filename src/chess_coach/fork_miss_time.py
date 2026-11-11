"""Match known game time controls across the two samples."""

import re
from collections import Counter


def _times(db, games):
    result = []
    for game in games:
        row = db.connection.execute(
            "SELECT time_control FROM games WHERE id=?", (game["id"],)
        ).fetchone()
        value = row[0] if row else None
        if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\+[0-9]+)?", value):
            return None
        base, _, increment = value.partition("+")
        if int(base) == 0 and (not increment or int(increment) == 0):
            return None
        result.append(value)
    return Counter(result)
