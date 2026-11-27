"""Choose only between comparable, verified capture observations."""

from .curriculum_capture_practice import evidence
from .curriculum_capture_source import practice_reason


def preferred(first, second):
    """Prefer a verified unmet capture only against a comparable verified result."""
    if first is None or second is None:
        return None
    if (first["context"], first["side"]) != (second["context"], second["side"]):
        return None
    if first["result"] == second["result"]:
        return None
    return 0 if first["result"] == "incorrect" else 1


def choice(db, subject, state, options, matched, check, *, root=None, report=None):
    if len(options) < 2 or any(report["limited"] for _, report in options):
        return 0, practice_reason(False)
    if not _eligible(options, matched, state["seen"]):
        return 0, practice_reason(False)
    first, second = (
        evidence(
            db,
            subject,
            state["corpus_version"],
            report["source"]["position_id"],
            report["history"],
            state["as_of"],
            check,
        )
        for _, report in options
    )
    selected = preferred(first, second)
    if selected is not None:
        return selected, practice_reason(True)
    from .curriculum_capture_context import choice as plan_choice

    return plan_choice(
        db, subject, state, root, options, (first, second), check, report=report
    ) or (
        0,
        practice_reason(False),
    )


def _eligible(options, matched, seen):
    keys = {item["prompt_key"] for item, _ in options}
    return len(keys) == 2 and keys.isdisjoint(matched | set(seen))
