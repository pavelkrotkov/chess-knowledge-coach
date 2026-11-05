"""Rank current short-mate lesson examples by completed prompt."""

FAMILY = "bounded-mate-observation-mapper"


def keys(preview, adaptive):
    if not adaptive:
        return set()
    return {
        str(example["evidence_id"])
        for group in preview["groups"]
        if _supported(group["lesson"])
        for example in group["lesson"]["examples"]
    }


def boards(preview, adaptive):
    if not adaptive:
        return set()
    return {
        _board(example)
        for group in preview["groups"]
        if _supported(group["lesson"])
        for example in group["lesson"]["examples"]
    }


def order(lesson, examples, rehearsed, adaptive):
    if adaptive and _supported(lesson):
        return sorted(examples, key=lambda example: _rank(example, rehearsed))
    return examples


def mark(result, examples, rehearsed, adaptive):
    if not result or not adaptive or result["kind"] != "short_mate":
        return
    selected = next(
        example for example in examples if example["evidence_id"] == result["evidence_id"]
    )
    result["short_progress"] = bool(rehearsed)
    result["short_revisited"] = _board(selected) in rehearsed.values()


def _supported(lesson):
    return (lesson["skill"], lesson["operation"], lesson["family"]) == (
        "calculation",
        "execute",
        FAMILY,
    )


def _board(example):
    return " ".join(example["fen"].split()[:4])


def _rank(example, rehearsed):
    return _board(example) in rehearsed.values(), str(example["evidence_id"]) in rehearsed
