"""Hash exact legacy or measured opening-course content."""

from .fact_fingerprint import canonical, digest
from .opening_unfamiliar_lesson import lesson

VERSION = "unfamiliar-opening-course-v1"
SELECTED_VERSION = "unfamiliar-opening-course-v2"
MEASURED_VERSION = "unfamiliar-opening-course-v3"


def payload(report, selection, measurement):
    chapters = [
        lesson(report, color, report[color]) for color in ("white", "black") if report[color]
    ]
    payload = {"schema": VERSION, "report": report, "chapters": chapters}
    if selection is not None:
        payload.update(schema=SELECTED_VERSION, selection=selection)
    legacy_version = digest(canonical(payload))
    if measurement:
        chapters = [lesson(report, selection["color"], report[selection["color"]], measurement)]
        payload.update(schema=MEASURED_VERSION, chapters=chapters, measurement=measurement)
    return payload, legacy_version


def result(payload, selection, legacy_version):
    value = {
        "version": digest(canonical(payload)),
        "report": payload["report"],
        "chapters": payload["chapters"],
    }
    if selection is not None:
        value["selection"] = selection
    if "measurement" in payload:
        value.update(measurement=payload["measurement"], legacy_version=legacy_version)
    return value
