"""Build a versioned ranked opening course from one qualified observation."""

from .opening_context_launch_guard import validate
from .opening_context_launch_preflight import preflight
from .opening_queue_budget import BrowserBudget
from .opening_ranked_course_payload import VERSION as VERSION
from .opening_ranked_course_payload import build_from_context as build_from_context


def preview(
    db,
    root,
    learner,
    choice,
    *,
    budget=None,
    deadline=None,
    with_context=False,
    selection=None,
    legacy=False,
    teaching=False,
):
    if selection is not None or legacy:
        raise ValueError("opening selection differs")
    if deadline is not None:
        budget = BrowserBudget(db) if budget is None else budget
        budget.expires = min(budget.expires, deadline)
    context = preflight(db, root, learner, choice, budget=budget)
    if teaching:
        from .opening_ranked_teaching import assemble
        from .opening_ranked_teaching_source import qualify

        qualification = qualify(context)
        course = assemble(context, qualification)
        context["teaching_qualification"] = qualification
    else:
        course = build_from_context(context)
    validate(context, db, root, learner)
    return (course, context) if with_context else course
