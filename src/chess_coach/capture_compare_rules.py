"""Validate capture mechanism and difficulty fields for cohort matching."""


def _geometry(value):
    return (
        isinstance(value, list)
        and len(value) == 2
        and any(value)
        and all(type(part) is int and 0 <= part <= 7 for part in value)
    )


def mechanism(value):
    if not isinstance(value, dict) or set(value) != {"mover", "target", "geometry"}:
        return False
    return (
        type(value["mover"]) is int
        and 1 <= value["mover"] <= 6
        and type(value["target"]) is int
        and 2 <= value["target"] <= 5
        and _geometry(value["geometry"])
    )


def ratings(context):
    rating, deviation = context.get("content_rating"), context.get("content_deviation")
    baseline = context.get("ranking_baseline")
    return (
        type(rating) is int
        and 0 <= rating < 4000
        and type(deviation) is int
        and 0 <= deviation < 4000
        and (baseline is None or (type(baseline) is int and 0 < baseline < 4000))
        and "ranking_baseline" in context
    )


def same(content, source):
    return content["mover"] == source["mover"] and content["target"] == source["target"]


def checksum(value):
    return isinstance(value, str) and bool(value)
