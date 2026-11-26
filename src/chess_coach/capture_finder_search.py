"""Search current ranked sources for a proved unfamiliar capture."""

from .capture_difficulty_binding import difficulty_scope
from .capture_finder_dispatch import accept_options, decorate
from .capture_finder_prepared import select as prove
from .capture_plan_sources import witnesses
from .related_capture import present
from .related_capture_legacy import choose
from .tactical_exposure_admission import filter_eligible

MAX_PROOFS = 12
PER_SOURCE_PROOFS = 4


def search(
    db,
    learner,
    subject,
    corpus,
    secret,
    groups,
    familiar,
    deadline,
    expired,
    *,
    expected=None,
    difficulty=None,
):
    checked = 0
    sources = iter(witnesses(db, learner, groups, stop=lambda: expired(deadline)))
    while checked < MAX_PROOFS:
        if expired(deadline):
            break
        source = next(sources, None)
        if source is None:
            break
        try:
            selection = choose(db, subject, source["position_id"], corpus, familiar, difficulty)
            selection = difficulty_scope(selection, difficulty)
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        if expired(deadline):
            break
        if selection is None:
            continue
        available = filter_eligible(db, subject, selection[3], 16)
        candidate, used = prove(
            db,
            (*selection[:3], available, *selection[4:]),
            deadline,
            min(PER_SOURCE_PROOFS, MAX_PROOFS - checked),
            expired,
            subject,
            familiar[1],
            corpus,
            difficulty,
            **accept_options(db, selection, expected, subject, familiar[1], difficulty),
        )
        checked += used
        if candidate is not None:
            one = (*selection[:3], [candidate], *selection[4:])
            result = present(one, None, secret=secret)
            result = decorate(result, expected, difficulty)
            return source["position_id"], result
    return None
