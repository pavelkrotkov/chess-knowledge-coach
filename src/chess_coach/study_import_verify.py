"""Verify complete Study content and persist its private receipt."""

from datetime import UTC, datetime

from .deep_selection_source import learner_key
from .study_chapter_modes import verify_modes
from .study_intent import save
from .study_inventory import named, verify_chapters
from .study_privacy import metadata
from .study_remote import StudyError
from .tactical_study_final import check as final_check
from .tactical_study_mode import require_entry
from .tactical_study_order import verify as verify_order


def finish(remote, path, state, chapters, check, match, strict):
    study = metadata(remote, state["study"])
    verify_chapters(study, state, chapters)
    ids = verify_order(study, state, chapters, complete=True) if strict else []
    exported = remote.export(state["study"])
    if not all(match(named(chapter, state, i), exported) for i, chapter in enumerate(chapters)):
        raise StudyError("Study read-back is incomplete")
    entry = verify_modes(remote, study, state, chapters, marker=state["marker"] if strict else None)
    if strict:
        require_entry(ids, entry)
        final_check(remote, state, chapters, ids, match)
    check()
    state["entry_chapter"] = entry
    if strict:
        state.update(
            chapter_ids=ids,
            chapter_modes=[chapter["mode"] for chapter in chapters],
            privacy_verified=True,
            anonymous_verified=True,
            ordered_verified=True,
            learner_key=learner_key(remote.learner),
        )
    state["complete"] = True
    state["verified_at"] = datetime.now(UTC).isoformat()
    save(path, state)
