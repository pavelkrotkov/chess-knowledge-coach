"""Recheck the recorded capture rating inputs against the current source."""

from .capture_compare_rules import ratings
from .common_practice_ratings import read as rating_inputs


def current(db, source, corpus):
    practice, turn = source["common_practice"], source["turn"]
    context = practice["context"]
    if not ratings(context) or context["ranking_baseline"] is None:
        return None
    actual = rating_inputs(db, corpus, practice["content_key"], turn["position_id"], turn["side"])
    expected = (
        context["ranking_baseline"],
        context["content_rating"],
        context["content_deviation"],
        context["corpus_checksum"],
    )
    if actual != expected:
        return None
    return {
        "baseline": context["ranking_baseline"],
        "rating": context["content_rating"],
        "deviation": context["content_deviation"],
        "checksum": context["corpus_checksum"],
        "admission": "harder" if "progression" in practice["binding"] else "ordinary",
    }


def compatible(db, capture, fork, corpus):
    left, right = capture["source"], fork
    a, b = left["turn"], right["turn"]
    if any(a[key] != b[key] for key in ("side", "time_control", "phase", "material")):
        return False
    first, second = current(db, left, corpus), right["controls"]
    if first is None or first["admission"] != second["admission"]:
        return False
    fork_context = right["practice"]["binding"]["assessment"]["context"]
    if (left["practice"]["controls"]["corpus"], first["checksum"]) != (
        corpus,
        fork_context["checksum"],
    ):
        return False
    return (first["rating"] // 200 - first["baseline"] // 200, first["deviation"] // 100) == (
        second["rating"] // 200 - second["baseline"] // 200,
        second["deviation"] // 100,
    )
