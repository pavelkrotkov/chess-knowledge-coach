"""Partition public candidate admission and retained material examples."""

from .opening_context_development_public import witness


def partition(items, eligibility, color):
    result = {"eligible": [], "proved": [], "rejected": [], "unknown": [], "witnesses": {}}
    for item in items:
        move = item["uci"]
        state = eligibility[move]
        if state == "materially_worse":
            result["rejected"].append(move)
        elif state != "admitted":
            result["unknown"].append({"move": move, "reason": state})
        elif found := witness(item, color):
            result["proved"].append(move)
            result["witnesses"][move] = found
        else:
            result["unknown"].append(
                {"move": move, "reason": "current_material_certificate_unavailable"}
            )
    return result
