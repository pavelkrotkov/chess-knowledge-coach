"""Compare source-qualified game opportunity presence for two practice contexts."""

from .capture_context_presence import sample
from .capture_context_source import bind
from .curriculum_capture_inputs import observe
from .curriculum_capture_source_identity import require
from .curriculum_capture_witnesses import candidates


def _bounds(report, source, check):
    newer = sample(report["newer"], source["wanted"], check)
    earlier = sample(report["earlier"], source["wanted"], check)
    if min(newer["decisions"], earlier["decisions"]) < 5:
        return None
    if min(newer["lower"], earlier["lower"]) < 3:
        return None
    return {"newer": newer, "earlier": earlier}


def _preferred(first, second):
    if first["lower"] * second["denominator"] > second["upper"] * first["denominator"]:
        return 0
    if second["lower"] * first["denominator"] > first["upper"] * second["denominator"]:
        return 1
    return None


def compare(db, subject, corpus, root, as_of, report, before, check):
    if (
        not report
        or not report.get("qualified")
        or not report.get("boundary")
        or report["historical"]
    ):
        return None
    options, _, identity, _ = candidates(db, subject, corpus, check)
    if len(options) != 2:
        return None
    turns = report["newer"]["root_details"] + report["earlier"]["root_details"]
    sources = [bind(db, subject, corpus, as_of, option, turns, check) for option in options]
    if any(source is None for source in sources):
        return None
    first, second = sources
    if (first["controls"], first["side"], first["tier"], first["time_control"]) != (
        second["controls"],
        second["side"],
        second["tier"],
        second["time_control"],
    ):
        return None
    bounds = [_bounds(report, source, check) for source in sources]
    if any(value is None for value in bounds):
        return None
    require(db, subject, identity, check)
    if observe(db, subject, root, check) != before:
        raise ValueError("capture comparison changed")
    newer = [value["newer"] for value in bounds]
    return {
        "sources": sources,
        "bounds": bounds,
        "preferred": _preferred(*newer),
        "tier": first["tier"],
    }
