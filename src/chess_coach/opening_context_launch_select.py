"""Select one learner-chosen, source-current opening experiment."""

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
    admission = None
    if provisional:
        development = parent["development"]
        fit = parent["fit"]
        if development["status"] == "provisional" and development.get("choice") == item["uci"]:
            admission = "development"
        elif fit["status"] == "supported" and fit.get("winner") == item["uci"]:
            admission = "fit"
        else:
            raise ValueError("opening recommendation unavailable")
    return parent, item, admission
