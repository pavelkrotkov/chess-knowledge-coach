"""Bind selected-recommendation teaching roles to their original source."""

from .fact_fingerprint import canonical, digest
from .opening_course_chapters import owned
from .opening_recommendation_selection import selection
from .opening_recommendation_text import annotate, note
from .opening_revision_roles import explanation as direct_explanation
from .opening_revision_roles import ungraded

LEGACY_SCHEMA = "opening-revision-course-v2"
VERSION = "opening-revision-course-v4"


def version(source_version, chapters, rationale):
    return digest(
        canonical(
            {
                "schema": VERSION,
                "course": source_version,
                "chapters": chapters,
                "rationale": rationale,
            }
        )
    )


def explanation(course):
    rationale, decision, choice = course["rationale"], course["decision"], course["choice"]
    report = {
        "branch": rationale["branch"],
        "revision_judgments": rationale["judgments"],
        "fork_nomination": rationale["nomination"],
    }
    selected = selection(report, decision["game_id"], decision["position_id"], choice["uci"])
    chapter = direct_explanation(decision, choice, course["experiment"])
    return annotate(chapter, note(choice, selected, report))


def three_roles(original):
    if original["schema"] != LEGACY_SCHEMA:
        raise ValueError("opening preview version differs")
    worked = owned(original["decision"], original["choice"], original["experiment"])
    chapters = [explanation(original), worked, *original["chapters"][1:]]
    if original["public_status"] == "available":
        chapters[-1] = ungraded(chapters[-1], original["decision"]["color"])
    return {
        **original,
        "schema": VERSION,
        "version": version(original["version"], chapters, original["rationale"]),
        "source_version": original["version"],
        "chapters": chapters,
    }


def checked_explanation(course):
    if (
        version(course["source_version"], course["chapters"], course["rationale"])
        != course["version"]
    ):
        raise ValueError("opening preview version differs")
    return explanation(course)
