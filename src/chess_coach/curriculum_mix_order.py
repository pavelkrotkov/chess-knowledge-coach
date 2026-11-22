"""Finite provenance pass followed by fair bounded source retries."""

SOURCES = ("capture", "fork", "public", "canonical")


def family(state):
    index, turn = state["family_index"], state["family_turn"]
    # The first pass rotates all three provenance categories, including both owned skills.
    if index < 4:
        return SOURCES[(turn + index) % 4]
    if index < 6:
        return ("public", "canonical")[index - 4]
    if index < 8:
        return ("capture", "fork")[(turn + index) % 2]
    return "new"


def advance(state):
    state["family_index"] += 1
    if state["v"] != 6:
        from .curriculum_cursor_families import current_family

        state["phase"] = current_family(state)
        return
    # A later bounded page revisits deferred families instead of declaring them absent.
    if state["family_index"] == 8 and _deferred(state):
        state["family_index"] = 4
    state["phase"] = family(state)


def _deferred(state):
    return any(
        state[key] == "deferred"
        for key in ("capture_mix", "fork_mix", "public_status", "canonical_status")
    )


def skip(state, phase, summary, prerequisite):
    index = state["family_index"]
    # The first pass admits one owned item; the second may add the other skill.
    if phase in {"capture", "fork"}:
        status = state[phase + "_mix"]
        if index < 4:
            return any(state[key] == "offered" for key in ("capture_mix", "fork_mix"))
        return status not in {"unchecked", "deferred"}
    if phase in {"public", "canonical"}:
        return index >= 4 and state[phase + "_status"] != "deferred"
    if state["public_binding"] is not None:
        return True
    return not _mate_relevant(state, summary, prerequisite)


def _mate_relevant(state, summary, prerequisite):
    # Missing evidence in one skill is not a general beginner or weakness claim.
    return (
        summary["state"] == "supported_weakness"
        or bool(prerequisite and prerequisite["state"] == "available")
        or state["canonical_context"] == "first_recorded"
    )


def record(state, phase, found, status, reason):
    if state["v"] != 6 or phase not in {"capture", "fork"}:
        return
    if found:
        value = "offered"
    elif reason and reason.endswith("_scan_incomplete"):
        value = "deferred"
    elif status in {"no_source", "duplicate", "already_scheduled"}:
        value = "exhausted"
    else:
        value = "unavailable"
    state[phase + "_mix"] = value


def action(state, phase, summary, prerequisite):
    if state["v"] == 6 and skip(state, phase, summary, prerequisite):
        return "stop" if phase == "new" else "next"
    if state["v"] == 5 and phase == "new" and state["public_binding"] is not None:
        return "stop"
    return "run"


def mark(progress, state, phase, found):
    if state["v"] == 6:
        progress["unpublished_phase"] = phase if found else None


def recovery(state, saved, progress, size):
    # The checkpoint phase owns an item until the shared deadline has passed.
    phase = saved["phase"] if saved["v"] in {5, 6} and saved["phase"] in SOURCES else state["phase"]
    completed = len(progress["items"]) > size or (
        saved["v"] == 6 and progress.get("unpublished_phase") == phase
    )
    return phase, completed
