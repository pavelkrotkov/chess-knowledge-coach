"""Search current ranked sources for a proved unfamiliar capture."""

from .capture_finder_proof import prove
from .capture_plan_sources import witnesses
from .related_capture import _selection, present

MAX_PROOFS = 12


def search(db, learner, subject, corpus, secret, groups, familiar, deadline, expired):
    checked = 0
    sources = iter(witnesses(db, learner, groups, stop=lambda: expired(deadline)))
    while checked < MAX_PROOFS:
        if expired(deadline):
            break
        source = next(sources, None)
        if source is None:
            break
        try:
            selection = _selection(
                db, subject, source["position_id"], corpus, familiar_data=familiar
            )
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        if expired(deadline):
            break
        if selection is None:
            continue
        candidate, used = prove(db, selection, deadline, MAX_PROOFS - checked, expired)
        checked += used
        if candidate is not None:
            one = (*selection[:3], [candidate], *selection[4:])
            result = present(one, None, secret=secret)
            result["items"][0]["assessment_available"] = True
            result["items"][0]["assessment_proved"] = True
            result["certified"] = True
            return source["position_id"], result
    return None
