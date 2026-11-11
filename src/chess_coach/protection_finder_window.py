"""Keep a stable bounded marker window across finder requests."""

from .protection_finder_sources import rows


def load(db, identity, state):
    page = rows(db, identity, state[1], state[3], state[5])
    if page and not state[5]:
        state[3:] = [page[0]["id"] + 1, page[0]["id"] + 1, page[-1]["id"]]
    pending = [row for row in page if row["id"] < state[4]]
    return page, pending


def advance(state):
    lower = state[5]
    state[3:] = [lower, lower, 0]
