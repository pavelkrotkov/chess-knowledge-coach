"""Validate the ordered chapter portion of a tactical Study receipt."""

import re


def _identity(ids, entry):
    if not isinstance(ids, list) or not ids:
        return False
    return (
        entry == ids[0]
        and len(set(ids)) == len(ids)
        and all(re.fullmatch(r"[A-Za-z0-9]{8}", item) for item in ids)
    )


def entry(state):
    ids, chapters, modes = (
        state.get("chapter_ids"),
        state.get("chapters"),
        state.get("chapter_modes"),
    )
    if not _identity(ids, state.get("entry_chapter")):
        return None
    if chapters != ["done"] * len(ids) or not isinstance(modes, list) or len(modes) != len(ids):
        return None
    if any(mode not in {"conceal", "gamebook"} for mode in modes):
        return None
    return ids[0]
