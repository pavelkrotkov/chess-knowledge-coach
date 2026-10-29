"""Compose bounded, source-linked coaching without diagnosing the learner."""

from .lesson_cues import CUES
from .lesson_mechanisms import describe
from .lesson_possible import MECHANISMS
from .lesson_source import source

VERSION = "coach-lesson-v1"


def qualification(family):
    text = (
        "These are provisional bounded observations, not a diagnosis of skill, intent or attention. "
        "Unreviewed sources remain unreviewed; later counterplay and overall safety may be unknown."
    )
    if family in {"pin-execute-mapper", "pin-prevent-mapper"}:
        text += " Pin mastery remains closed; the displayed lines are bounded, not proof of overall safety."
    if family in {"pawn-structure-lesson-mapper", "rook-plan-lesson-mapper"}:
        text += " These are ambiguous descriptive observations, not skill evidence; repeated positions are not repeated mistakes. Plans are ideas and mastery remains closed."
    if family == "king-safety-lesson-mapper":
        text += " Shelter changes are not necessarily mistakes; compensation and later threats remain unresolved. Mastery remains closed."
    return text


def build(db, learner, group):
    examples = []
    for candidate in group["lesson_examples"]:
        inspected = source(db, learner, candidate)
        if inspected:
            item = describe(inspected)
            if item:
                item["context"] = candidate["context"]
                examples.append(item)
        if len(examples) == 3:
            break
    question, habit, practice = CUES[group["family"]]
    return {
        "version": VERSION,
        "skill": group["skill"],
        "operation": group["operation"],
        "family": group["family"],
        "source_version": group["version"],
        "examples": examples,
        "possible": MECHANISMS[group["family"]],
        "question": question,
        "habit": habit,
        "practice": practice,
        "qualification": qualification(group["family"]),
    }
