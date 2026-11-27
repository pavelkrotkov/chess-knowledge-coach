"""Explain a selected ranked opening using only its checked context."""

from .opening_context_display import _path
from .opening_unfamiliar_course_text import tree as source_tree
from .opening_unfamiliar_lesson import _geometry


def _fit(parent):
    fit = parent["fit"]
    names = {item["uci"]: item["san"] for item in parent["items"]}
    if fit["status"] == "supported":
        result = (
            f"The early-center comparison favored {names[fit['winner']]} "
            f"for the checked games and matching time control {fit['control']}. "
        )
    elif fit["status"] == "tie":
        result = "The early-center comparison did not distinguish the checked moves. "
    else:
        result = "The checked games do not establish an early-center fit winner. "
    labels = {
        "admitted": "included in the comparison",
        "materially_worse": "outside the bounded comparison threshold",
        "seen_in_checked_sample": "already seen in the checked games",
    }
    alternatives = "; ".join(
        f"{item['san']}: {labels.get(fit['choices'].get(item['uci']), 'not established')}"
        for item in parent["items"]
    )
    return result + f"Checked alternatives: {alternatives}. "


def _development(parent):
    value = parent["development"]
    if value["status"] == "provisional":
        name = next(item["san"] for item in parent["items"] if item["uci"] == value["choice"])
        return (
            f"A checked public fork after {name} makes it a provisional learning experiment "
            f"alongside {value['owned']['games']} independent games with accepted evidence reviews. "
            "The wider public sample is incomplete; other choices may lack a verified fork example. "
        )
    if value["status"] == "tie":
        return "The checked developmental examples do not distinguish the alternatives. "
    return "A developmental ordering is not established by the checked evidence. "


def ranked(context):
    item, parent = context["item"], context["parent"]
    selection = item["selection"]
    return (
        f"You play {selection['color'].capitalize()} after {_path(selection['path'])}; "
        f"your selected move is {item['san']}. "
        + _fit(parent)
        + _development(parent)
        + source_tree(item, parent)
        + _geometry(item["source"]["profile"])
        + " Rehearsal: replay the selected line and compare the checked responses and structures. "
        "The recorded continuation is ungraded; other legal choices are not assessed. "
        "Wider strategic plans and demands remain unknown. The bounded sample does not "
        "establish opening soundness, personal preference, mastery or a cause of mistakes. "
        "History outside the checked sample remains unknown."
    )
