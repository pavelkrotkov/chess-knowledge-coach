"""Revalidate all saved examples behind a repeated coaching claim."""

from .lesson_mechanisms import describe
from .lesson_source import source


def revalidate_group(db, learner, group):
    lesson = group["lesson"]
    games = set()
    for example in lesson["examples"]:
        current = source(
            db, learner, {"id": example["evidence_id"], "position_id": example["position_id"]}
        )
        if not current or not _same(current, lesson, example):
            raise ValueError("coaching lesson evidence changed")
        games.add(example["game_id"])
    if len(games) < 2:
        raise ValueError("repeated coaching evidence is unavailable")
    return len(games)


def _same(current, lesson, example):
    evidence = current["evidence"]
    expected = (lesson["skill"], lesson["operation"], lesson["family"], "failure")
    actual = (
        evidence["skill"],
        evidence["operation"],
        evidence["mapping_producer"],
        evidence["outcome"],
    )
    if actual != expected or evidence["facts"][0]["detector_version"] != lesson["source_version"]:
        return False
    refreshed = describe(current)
    return refreshed is not None and all(
        example.get(key) == value for key, value in refreshed.items()
    )
