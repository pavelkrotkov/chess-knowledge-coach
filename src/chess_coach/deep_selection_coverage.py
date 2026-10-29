"""Summarize nomination and control coverage for one bounded selection."""

from collections import Counter

from .deep_selection_categories import CATEGORIES, categories


def coverage(ordered, selected, targets, controls, limit):
    nominated = _category_counts(ordered)
    selected_categories = _category_counts(selected)
    allocations = Counter(item["allocation"] for item in selected)
    return {
        "eligible": len(ordered),
        "missing_scores": sum("score_unavailable" in item["reasons"] for item in ordered),
        "overlapping_nominations": sum(len(categories(item["reasons"])) > 1 for item in ordered),
        **_categories_summary(nominated, selected_categories, allocations, targets),
        **_reason_summary(ordered, selected),
        "control_pool": sum(not categories(item["reasons"]) for item in ordered),
        "control_target": controls,
        "control_selected": allocations["control"],
        "selected": len(selected),
        "capped_out": len(ordered) - len(selected),
        "omitted_critical": _omitted_critical(ordered, selected),
        "effective_limit": limit,
    }


def _category_counts(items):
    return Counter(category for item in items for category in categories(item["reasons"]))


def _omitted_critical(ordered, selected):
    ids = {item["position_id"] for item in selected}
    return sum(
        bool(categories(item["reasons"])) and item["position_id"] not in ids for item in ordered
    )


def _categories_summary(nominated, selected, allocations, targets):
    return {
        "nominated": {category: nominated[category] for category in CATEGORIES},
        "selected_by_category": {category: selected[category] for category in CATEGORIES},
        "omitted_by_category": {
            category: nominated[category] - selected[category] for category in CATEGORIES
        },
        "quota_targets": targets,
        "quota_allocated": {category: allocations[category] for category in CATEGORIES},
    }


def _reason_summary(ordered, selected):
    nominated = Counter(reason for item in ordered for reason in item["reasons"])
    chosen = Counter(reason for item in selected for reason in item["reasons"])
    return {
        "reason_counts": dict(sorted(nominated.items())),
        "omitted_reason_counts": {
            reason: count - chosen[reason] for reason, count in sorted(nominated.items())
        },
    }
