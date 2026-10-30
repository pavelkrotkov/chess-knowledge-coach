"""Summarize bounded native job work without inferring missing counters."""

from .purpose_config import FINAL_NODES, SCOUT_NODES


def summary(items):
    searches = _searches(items)
    return {
        "job_limit": 3,
        "search_limit": 6,
        "requested_node_limit": 3 * (SCOUT_NODES + FINAL_NODES),
        "jobs_considered": len(items),
        "searches_observed": len(searches),
        "requested_nodes_observed_lower_bound": sum(
            item["requested_nodes"] or 0 for item in searches
        ),
        "actual_nodes_observed_lower_bound": sum(item["actual_nodes"] or 0 for item in searches),
        "searches_with_overshoot": sum(item["overshoot"] is True for item in searches),
        "work_unknown": any(item.get("work", {}).get("unknown", True) for item in items),
    }


def _searches(items):
    return [search for item in items for search in item.get("work", {}).get("searches", [])]
