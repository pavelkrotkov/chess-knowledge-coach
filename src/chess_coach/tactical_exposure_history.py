"""Match a historical tactical intent only to an exact owner-bound export."""

from .mastery_time import parse_utc
from .tactical_export_input import load
from .tactical_exposure_historical_positions import positions as historical_positions
from .tactical_exposure_pointer import pointer
from .tactical_study_preview import preview
from .tactical_study_receipt import exact


def historical(root, directory, database, subject, version, state, target, cutoff):
    path = pointer(directory, database, subject, version)
    if path is None:
        return "legacy_coverage_unknown"
    envelope = load(root, path)
    preview(envelope, version)
    course = envelope["export"]
    positions = historical_positions(course, state)
    if positions is None:
        return "coverage_unavailable"
    if target not in positions:
        return "not_recorded"
    if not exact(directory, subject, version, course):
        return "publication_time_unknown"
    verified = parse_utc(state.get("verified_at"))
    if verified is None:
        return "publication_time_unknown"
    return "provided" if verified <= cutoff else "publication_time_unknown"
