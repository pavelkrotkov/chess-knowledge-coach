"""Retain compact game context with a verified calendar date."""

from datetime import datetime


def _date(headers):
    for key in ("Date", "UTCDate"):
        value = headers.get(key, "")
        try:
            parsed = datetime.strptime(value, "%Y.%m.%d")
            if parsed.strftime("%Y.%m.%d") == value:
                return value
        except ValueError:
            pass
    return "?"


def context_for(headers):
    context = {key: headers.get(key, "?")[:200] for key in ("Event", "White", "Black", "Result")}
    context["Date"] = _date(headers)
    return context
