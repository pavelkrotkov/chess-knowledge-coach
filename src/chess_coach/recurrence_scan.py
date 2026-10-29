"""Walk one bounded evidence page and stop at the game replay budget."""

from .recurrence_selection import consider


def scan(
    db, learner, rows, sources, cache, parts, excluded, found, begin, finish, previous, *, single
):
    for row in rows:
        blocked = excluded["game replay limit"]
        item = consider(db, learner, row, sources, cache, parts, excluded, begin, finish, previous)
        if item:
            found.append(item)
        if single and excluded["game replay limit"] > blocked:
            return row["id"] + 1
    return None
