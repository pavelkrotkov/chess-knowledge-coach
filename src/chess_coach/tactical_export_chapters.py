"""Rebuild and compare the exact source-linked worked chapters."""

from .course_guidance import challenge
from .objective_fork_contract import VERSION as LEGACY_FORK_VERSION
from .tactical_course_familiar import familiarity
from .tactical_course_protection import source as teaching_source
from .tactical_course_related import unfamiliar
from .tactical_course_resolve import related as current_related
from .tactical_export_compare import compare
from .tactical_export_sources import choice, verify_owned


def verify(
    db,
    subject,
    corpus,
    pattern,
    lesson,
    chapters,
    budget,
    *,
    modern=False,
    thematic=False,
    artifact=None,
    named=False,
    roles=False,
):
    owned_saved = chapters[1] if roles else chapters[0]
    selected = _selected(db, subject, pattern, lesson, owned_saved, budget, modern)
    verify_owned(db, subject, pattern, lesson, chapters, budget, selected, roles)
    if len(chapters) == (2 if roles else 1):
        return
    _related(
        db,
        subject,
        corpus,
        selected,
        chapters[-1],
        budget,
        modern,
        thematic,
        artifact,
        named,
        roles,
    )


def _is_thematic(chapter, enabled):
    if not enabled:
        return False
    from .tactical_course_thematic import VERSION as THEMATIC_BINDING

    return chapter["source"].get("binding", {}).get("version") == THEMATIC_BINDING


def _related(
    db, subject, corpus, selected, saved, budget, modern, thematic, artifact, named, roles
):
    if named:
        related, _ = current_related(
            db, subject, corpus, selected, budget, thematic=True, artifact=artifact, named=True
        )
    elif _is_thematic(saved, thematic):
        related, _ = current_related(
            db, subject, corpus, selected, budget, thematic=True, artifact=artifact
        )
    else:
        source = None
        if modern and selected["kind"] == "protection":
            with budget.scope(snapshot=True):
                source = teaching_source(db, subject, selected)
        familiar_data = familiarity(db, subject, budget)
        with budget.scope(snapshot=False):
            options = {"teaching_source": source} if source is not None else {}
            related = unfamiliar(
                db, subject, corpus, selected, familiar_data=familiar_data, **options
            )
    if related is None:
        raise ValueError("related source unavailable")
    if roles:
        related = {**related, "role": "practice"}
    with budget.scope(snapshot=False):
        compare(saved, related, gamebook=named)


def _selected(db, subject, pattern, lesson, chapter, budget, modern):
    selected = choice(db, subject, lesson, budget)
    if selected["kind"] != pattern["kind"] or pattern["local_challenge"] != challenge(
        selected, protection=modern
    ):
        raise ValueError("selected source differs")
    # Existing worked chapters retain the source version they recorded.
    if selected["kind"] == "fork" and chapter["source"]["version"] == LEGACY_FORK_VERSION:
        selected = {**selected, "version": LEGACY_FORK_VERSION}
    return selected
