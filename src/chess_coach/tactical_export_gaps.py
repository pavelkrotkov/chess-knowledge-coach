"""Check selected patterns against their recorded coverage and omissions."""

from .tactical_course_selection import PAIRS

OWN = "owned source unavailable"
UNSUPPORTED = "related matching unsupported"
RELATED = {
    UNSUPPORTED,
    "related matching deferred: time budget",
    "related corpus or compatible unfamiliar example unavailable",
}


def omissions(selection):
    result = {}
    coverage = {(row["skill"], row["operation"]): row for row in selection["coverage"]}
    for item in selection["unavailable"]:
        pair = (item["skill"], item["operation"])
        reason = item["reason"]
        if pair not in PAIRS or pair in result or reason not in RELATED | {OWN}:
            raise ValueError("invalid preview omission")
        if coverage[pair]["status"] != "complete":
            raise ValueError("omission has incomplete coverage")
        result[pair] = reason
    return result


def selected(pattern, chapters, gaps):
    pair = (pattern["skill"], pattern["operation"])
    reason = gaps.get(pair)
    if reason == OWN or (reason is None) != (len(chapters) == 2):
        raise ValueError("related chapter and omission differ")
    if (reason == UNSUPPORTED) != (pattern["kind"] == "protection"):
        raise ValueError("unsupported related pattern differs")
