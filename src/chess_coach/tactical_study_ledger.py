"""Reject malformed version ledgers before any tactical provider request."""

from .study_remote import StudyError


def _states(values, complete):
    if any(value not in {"new", "pending", "done"} for value in values):
        return False
    return not complete or all(value == "done" for value in values)


def validate(state, chapters):
    values = state.get("chapters")
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 63:
        raise StudyError("unsupported tactical chapter count")
    if not isinstance(values, list) or len(values) != len(chapters):
        raise StudyError("tactical chapter ledger differs")
    complete = state.get("complete")
    if type(complete) is not bool or not _states(values, complete):
        raise StudyError("tactical chapter ledger differs")


def validate_owned(state, course, owner):
    """Recheck the exact owner's current course ledger between publication steps."""
    if state.get("course_sha256") != course["course_sha256"] or state.get("learner_key") not in (
        None,
        owner,
    ):
        raise StudyError("Study intent identity differs")
    delivery = state.get("tactical_delivery")
    if delivery is not None and (
        delivery.get("owner") != owner or delivery.get("version") != "tactical-study-exposure-v1"
    ):
        raise StudyError("Study intent owner differs")
    validate(state, course["course"]["chapters"])
