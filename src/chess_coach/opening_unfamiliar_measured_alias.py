"""Reconstruct exact measured variants from the same freshly verified source."""

from .opening_unfamiliar_course import legacy_from
from .opening_unfamiliar_course_payload import payload as make_payload
from .opening_unfamiliar_course_payload import result as result_value


def measured_alias(value, expected):
    measurement, decision = value.get("measurement"), value.get("_decision")
    if not measurement or not decision or value["version"] == expected:
        return value
    alternate = {key: item for key, item in measurement.items() if key != "decision"}
    if "decision" not in measurement:
        alternate["decision"] = decision
    payload, legacy_version = make_payload(value["report"], value["selection"], alternate)
    result = result_value(payload, value["selection"], legacy_version)
    if result["version"] != expected:
        return value
    result["_decision"] = decision
    return result


def historical(value, selection, expected):
    if not expected or not selection:
        return value
    value = measured_alias(value, expected)
    if value.get("legacy_version") == expected:
        value = legacy_from(value)
        value["historical"] = True
    return value
