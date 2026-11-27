"""Keep prerequisite policy binding across a source refresh."""

from .curriculum_prerequisite_source import POLICY, graph


def check_policy(state):
    if (state["prerequisite_policy"], state["prerequisite_graph"]) != (POLICY, graph()):
        raise ValueError("curriculum prerequisite policy changed; restart the plan")


def check_window(value):
    from .curriculum_priority_cursor import COMMON_POLICY

    if value["state"].get("priority_policy") == COMMON_POLICY and value["goal"] != "balanced":
        raise ValueError("unsupported common window")


def common_renewal(policy, prior_minutes, minutes, budget):
    from .curriculum_priority_cursor import COMMON_POLICY

    if policy == COMMON_POLICY:
        if (prior_minutes is None and minutes is not None) or budget is None:
            raise ValueError("start a new timed plan")
        from .tactical_course_budget import SLICE_SECONDS

        budget.expires = min(budget.expires, budget.common_started + SLICE_SECONDS)
