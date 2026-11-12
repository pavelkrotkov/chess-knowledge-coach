"""Apply established sample thresholds and recorded-context checks."""

from .mastery_time import parse_utc
from .mate_assessment_compare import SAMPLE, comparable


def check(values, limited):
    if not comparable(values, limited):
        return (
            "Two ordered samples each need 10 current, resolved, unassisted first checks.",
            None,
        )
    first, last = values[:SAMPLE], values[-SAMPLE:]
    opening = _opening(first, last)
    if opening["mismatch"]:
        return "Recorded opening contexts differ between the samples.", opening
    if max(_time(item["answered_at"]) for item in first) >= min(
        _time(item["started_at"]) for item in last
    ):
        return "The assessment intervals overlap.", opening
    return None, opening


def _tags(items):
    return {tag for item in items for tag in (item["opening"] or "").split()}


def _known(items):
    return sum(bool((item["opening"] or "").split()) for item in items)


def _opening(first, last):
    earlier, later = _tags(first), _tags(last)
    return {
        "earlier_known": _known(first),
        "later_known": _known(last),
        "mismatch": bool(earlier and later and earlier.isdisjoint(later)),
        "partial": bool(earlier & later and earlier != later),
    }


def _time(value):
    result = parse_utc(value)
    if result is None:
        raise ValueError("recognition time unavailable")
    return result
