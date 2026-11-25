"""Keep prerequisite policy binding across a source refresh."""

from .curriculum_prerequisite_source import POLICY, graph


def check_policy(state):
    if (state["prerequisite_policy"], state["prerequisite_graph"]) != (POLICY, graph()):
        raise ValueError("curriculum prerequisite policy changed; restart the plan")
