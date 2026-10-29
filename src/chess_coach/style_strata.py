"""Stratify observed choices by explicitly recorded context."""

from collections import defaultdict

from .style_counts import counts


def strata(items, dimension):
    groups = defaultdict(list)
    keys = (
        "color",
        "rating",
        "opponent_rating",
        "time_control",
        "clock_band",
        "phase",
        "familiarity",
    )
    for item in items:
        for key in keys:
            groups[(key, item["context"][key])].append(item)
        groups[("allocation", item["allocation"])].append(item)
        groups[("opening", item["context"]["opening"]["name"])].append(item)
        for family in item["context"]["structures"] or ["no named match"]:
            groups[("structure", family)].append(item)
    return [
        {"field": key[0], "value": key[1], **counts(group, dimension)}
        for key, group in sorted(groups.items())
    ]
