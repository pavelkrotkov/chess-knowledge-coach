"""Derive a read-only opening course version from the checked report and chapters."""

from .opening_unfamiliar import explore_unfamiliar
from .opening_unfamiliar_course_payload import (
    MEASURED_VERSION as MEASURED_VERSION,
)
from .opening_unfamiliar_course_payload import SELECTED_VERSION as SELECTED_VERSION
from .opening_unfamiliar_course_payload import VERSION as VERSION
from .opening_unfamiliar_course_payload import payload as _payload
from .opening_unfamiliar_course_payload import result as _result


def _source(db, root, learner, selection, legacy, deadline):
    if selection is None:
        return explore_unfamiliar(db, root, learner), None
    from .opening_unfamiliar_selected import selected

    if legacy:
        return selected(db, root, learner, selection, deadline=deadline), None
    return selected(db, root, learner, selection, measured=True, deadline=deadline)


def preview(db, root, learner, selection=None, *, legacy=False, deadline=None):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    report, measurement = _source(db, root, learner, selection, legacy, deadline)
    if measurement:
        from .opening_unfamiliar_course_proof import current_stamp

        if not current_stamp(db, root, learner, measurement):
            measurement = None
        else:
            measurement = {
                key: value for key, value in measurement.items() if key != "source_stamp"
            }
    payload, legacy_version = _payload(report, selection, measurement)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("opening course source changed")
    return _result(payload, selection, legacy_version)


def legacy_from(value):
    selection = value["selection"]
    payload, version = _payload(value["report"], selection, None)
    if version != value.get("legacy_version"):
        raise ValueError("previous opening version differs")
    result = _result(payload, selection, version)
    result["_measurement_source"] = value["measurement"]["source_identity"]
    return result
