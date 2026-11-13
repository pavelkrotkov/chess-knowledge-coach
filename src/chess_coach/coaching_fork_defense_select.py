"""Admit at most one displayed fork-prevention source of each origin."""

from .coaching_fork_defense_identity import identity
from .coaching_practice_source import resolve_example


def _kind(example):
    if example.get("anchored_fork_prevention"):
        return "fork_defense"
    if example.get("created_fork_avoidance"):
        return "fork_avoidance"
    return None


def examples(db, subject, lesson, budget):
    output, kinds = {}, set()
    for example in lesson["examples"]:
        if len(kinds) == 2:
            break
        kind = _kind(example)
        if kind is None or kind in kinds:
            continue
        try:
            with budget.scope(snapshot=False):
                action = resolve_example(db, subject, lesson, example, identity_for=identity)
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        if action and action["kind"] == kind:
            output[action["evidence_id"]] = action
            kinds.add(action["kind"])
    return output
