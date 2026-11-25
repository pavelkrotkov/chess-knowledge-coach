"""Partition public candidate admission and retained material examples."""

from .opening_context_development_public import witness


def _witness(item, color):
    try:
        return witness(item, color)
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def _unknown(item):
    proof = item["public_fork"]
    if proof["status"] != "prepared":
        return "certificate_" + proof["status"]
    status = proof["coverage"]["status"]
    return "certificate_" + status if status != "checked" else "material_certificate_unavailable"


def partition(items, eligibility, color):
    result = {
        "eligible": [],
        "proved": [],
        "rejected": [],
        "unknown": [],
        "witnesses": {},
        "tied": [],
        "provisional": [],
    }
    for item in items:
        move = item["uci"]
        state = eligibility[move]
        if state == "materially_worse":
            result["rejected"].append(move)
        elif state != "admitted":
            result["unknown"].append({"move": move, "reason": state})
        elif found := _witness(item, color):
            result["proved"].append(move)
            result["witnesses"][move] = found
        else:
            result["unknown"].append({"move": move, "reason": _unknown(item)})
    return result
