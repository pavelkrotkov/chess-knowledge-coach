"""Summarize bounded discovery-defense work without source identifiers."""

from collections import Counter


def _counter(lanes, key):
    return dict(sorted(sum((lane[key] for lane in lanes.values()), Counter()).items()))


def _normalize(lanes, key):
    for lane in lanes.values():
        lane[key] = dict(sorted(lane[key].items()))


def _status(lane):
    if not lane["scanned"]:
        return "not_scanned"
    if lane["unavailable"] or lane["source_unavailable"] or lane["capped"]:
        return "partial"
    return "scanned"


def summarize(lanes, limits):
    result = {
        key: sum(lane[key] for lane in lanes.values())
        for key in ("examined", "processed", "replayed", "unavailable")
    }
    result["capped"] = any(lane["capped"] for lane in lanes.values())
    result["status"] = "partial" if result["capped"] or result["unavailable"] else "complete"
    result["limits"] = limits
    for key in ("outcomes", "material_unresolved", "success_coverage"):
        result[key] = _counter(lanes, key)
        _normalize(lanes, key)
    for lane in lanes.values():
        lane["status"] = _status(lane)
    result.update(lanes)
    return result
