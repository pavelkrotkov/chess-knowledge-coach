"""Choose only between comparable, verified capture observations."""

from .curriculum_capture_practice import evidence


def preferred(first, second):
    """Prefer a verified unmet capture only against a comparable verified result."""
    if first is None or second is None:
        return None
    if (first["context"], first["side"]) != (second["context"], second["side"]):
        return None
    if first["result"] == second["result"]:
        return None
    return 0 if first["result"] == "incorrect" else 1


def _practice(db, subject, corpus, state, option, check):
    _, report = option
    return evidence(
        db,
        subject,
        corpus,
        report["source"]["position_id"],
        report["history"],
        state["as_of"],
        check,
    )


def choice(db, subject, state, options, matched, check):
    if len(options) < 2 or any(report["limited"] for _, report in options):
        return 0, False
    if not _eligible(options, matched, state["seen"]):
        return 0, False
    first, second = (
        _practice(db, subject, state["corpus_version"], state, item, check) for item in options
    )
    selected = preferred(first, second)
    return (0, False) if selected is None else (selected, True)


def _eligible(options, matched, seen):
    keys = [item["prompt_key"] for item, _ in options]
    return len(set(keys)) == 2 and not any(key in matched or key in seen for key in keys)
