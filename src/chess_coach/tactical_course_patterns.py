"""Revalidate and assemble a small ordered set of tactical patterns."""

from .course_guidance import challenge
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_capture_roles import compose
from .tactical_course_resolve import own, related

MAX_PATTERNS = 3


def _pattern(group, choice, bindings):
    lesson = group["lesson"]
    return {
        "skill": lesson["skill"],
        "operation": lesson["operation"],
        "family": lesson["family"],
        "kind": choice["kind"],
        "independent_games": len({item["game_key"] for item in bindings}),
        "supporting_sources": bindings,
        "inspected_misses": group["misses"],
        "review_states": [item["review"] for item in lesson["examples"]],
        "local_challenge": challenge(choice, protection=True),
    }


def assemble(
    db,
    subject,
    corpus,
    groups,
    budget,
    *,
    allow_empty=False,
    thematic=False,
    named=False,
    roles=False,
    fork=False,
    protection=False,
):
    patterns, chapters, unavailable = [], [], []
    for index, group in enumerate(groups):
        if len(patterns) >= MAX_PATTERNS:
            return patterns, chapters, unavailable, len(groups) - index
        pair = {"skill": group["lesson"]["skill"], "operation": group["lesson"]["operation"]}
        result = own(db, subject, group, budget)
        if not isinstance(result, tuple):
            unavailable.append({**pair, "reason": result or "owned source unavailable"})
            continue
        choice, own_chapter, bindings = result
        patterns.append(_pattern(group, choice, bindings))
        item, reason, chapters_for_pattern = _chapters(
            db,
            subject,
            corpus,
            choice,
            own_chapter,
            budget,
            thematic=thematic,
            named=named,
            roles=roles,
            fork=fork,
            protection=protection,
        )
        if item is None:
            unavailable.append({**pair, "reason": reason})
        chapters.extend(chapters_for_pattern)
    _require_patterns(patterns, allow_empty)
    return patterns, chapters, unavailable, 0


def _chapters(
    db, subject, corpus, choice, owned, budget, *, thematic, named, roles, fork, protection
):
    if fork and choice["kind"] == "fork":
        from .tactical_course_fork_practice import related as fork_related
        from .tactical_course_fork_roles import compose as fork_compose

        item, reason = fork_related(db, subject, corpus, choice, budget)
        # Saved v11 courses keep two roles; newer versions add the explanation.
        return item, reason, fork_compose(owned, item, budget, roles)
    item, reason = related(db, subject, corpus, choice, budget, thematic=thematic, named=named)
    if protection:
        from .tactical_course_protection_roles import compose as protection_compose

        return item, reason, protection_compose(owned, item)
    return item, reason, compose(choice, owned, item, roles)


def _require_patterns(patterns, allow_empty):
    if not patterns and not allow_empty:
        raise PreviewUnavailable("no supported recurring patterns")
