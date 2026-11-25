"""Attach an owner-selected opening to an independently eligible plan task."""

from .curriculum_cursor import revision
from .opening_context_display import _path
from .opening_context_launch_guard import validate
from .opening_context_launch_match import eligible
from .opening_context_launch_scope import result as result_scope
from .opening_context_launch_token import issue_context, issue_launch
from .tactical_exposure_practice import check as exposure


def attach(db, root, subject, corpus, current, plan):
    scope = result_scope(plan)
    detail = _detail(current)
    detail["token"] = issue_context(db, subject, current, scope)
    plan["opening_context"] = detail
    item = eligible(current, plan["items"])
    if item is not None:
        history = exposure(db, subject, item["prompt_key"])
        if history in {"clear", "history_unknown"}:
            item["opening_token"] = issue_launch(
                db, subject, current, item, history, scope, revision(db), corpus
            )
            detail["status"] = "offered"
            detail["exposure"] = history
    validate(current, db, root, subject)


def _detail(current):
    item, selection = current["item"], current["item"]["selection"]
    return {
        "status": "unavailable",
        "name": item["name"],
        "move": item["san"],
        "color": selection["color"],
        "context": _path(selection["path"]),
        "fit_status": current["parent"]["fit"]["status"],
        "fit_reason": current["parent"]["fit"]["reason"],
        "source": item["source"]["line"]["site"] or item["source"]["profile"]["source"],
        "license": item["source"]["profile"]["license"],
        "license_url": item["source"]["profile"]["license_url"],
    }
