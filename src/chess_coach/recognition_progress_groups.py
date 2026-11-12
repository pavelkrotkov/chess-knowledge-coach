"""Compare disjoint matched recognition samples without causal claims."""

from collections import defaultdict

from .mate_assessment_compare import SAMPLE
from .mate_assessment_group_counts import counts
from .recognition_progress_compare import check


def groups(items, limited):
    grouped = defaultdict(list)
    for item in items:
        if item.get("scope"):
            grouped[item["scope"]["key"]].append(item)
    return [_group(values, limited) for values in grouped.values()]


def _group(values, limited):
    first, last = values[:SAMPLE], values[-SAMPLE:]
    result = {
        **{key: values[0]["scope"][key] for key in ("kind", "color", "rating", "deviation")},
        "count": len(values),
        "baseline": counts(first),
        "baseline_opening": sum(bool((item["opening"] or "").split()) for item in first),
        "comparable": False,
    }
    reason, opening = check(values, limited)
    if reason:
        result.update(reason=reason, opening=opening)
        return result
    earlier, later = counts(first), counts(last)
    a, b = earlier["unassisted"].get("verified", 0), later["unassisted"].get("verified", 0)
    result.update(
        comparable=True,
        earlier=earlier,
        later=later,
        opening=opening,
        direction="more" if b > a else "fewer" if b < a else "equal",
        recognition_end=max(item["answered_at"] for item in last),
    )
    return result
