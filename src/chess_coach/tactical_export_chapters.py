"""Rebuild and compare the exact source-linked worked chapters."""

from .course_guidance import challenge
from .tactical_course_chapters import owned_chapter
from .tactical_course_familiar import familiarity
from .tactical_course_protection import source as teaching_source
from .tactical_course_related import unfamiliar
from .tactical_export_compare import compare
from .tactical_export_sources import choice


def verify(db, subject, corpus, pattern, lesson, chapters, budget, *, modern=False):
    selected = choice(db, subject, lesson, budget)
    if selected["kind"] != pattern["kind"] or pattern["local_challenge"] != challenge(
        selected, protection=modern
    ):
        raise ValueError("selected source differs")
    with budget.scope(snapshot=True):
        owned = owned_chapter(
            db, subject, {"lesson": lesson}, selected, pattern["supporting_sources"]
        )
    with budget.scope(snapshot=False):
        compare(chapters[0], owned)
    if len(chapters) == 1:
        return
    source = None
    if modern and selected["kind"] == "protection":
        with budget.scope(snapshot=True):
            source = teaching_source(db, subject, selected)
    familiar_data = familiarity(db, subject, budget)
    with budget.scope(snapshot=False):
        options = {"teaching_source": source} if source is not None else {}
        related = unfamiliar(db, subject, corpus, selected, familiar_data=familiar_data, **options)
        if related is None:
            raise ValueError("related source unavailable")
        compare(chapters[1], related)
