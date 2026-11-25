"""Select one learner-chosen, current provisional opening experiment."""

from .opening_context_choice import reason, token


def selected(report, choice, *, provisional):
    if report.get("status") != "prepared":
        raise ValueError("opening context unavailable")
    for group in report["contexts"].values():
        for parent in group["parents"]:
            for item in parent["items"]:
                if token(item["selection"]) == choice:
                    return _selected(report, parent, item, provisional)
    raise ValueError("opening selection changed")


def _selected(report, parent, item, provisional):
    if reason(report, item) != "available":
        raise ValueError("opening selection unavailable")
    if provisional:
        judgment = parent["development"]
        if judgment["status"] != "provisional" or judgment["choice"] != item["uci"]:
            raise ValueError("opening development unavailable")
    return parent, item
