"""Validate the sidecar envelope and examined source sequence."""

from .short_mate_trend_records import games, retained


def _source(row):
    return (
        isinstance(row, list)
        and len(row) == 2
        and type(row[0]) is int
        and row[0] > 0
        and isinstance(row[1], str)
    )


def _checked(data):
    checked = data.get("checked")
    if not isinstance(checked, list) or len(checked) > 100:
        return False
    if type(data.get("index")) is not int or data["index"] != len(checked):
        return False
    return all(map(_source, checked))


def _metadata(data):
    return (
        isinstance(data.get("frontier"), str)
        and type(data.get("selection_complete")) is bool
        and type(data.get("rotation", 0)) is int
        and type(data.get("unavailable")) is int
        and type(data.get("duplicates")) is int
    )


def valid(data, expected):
    if not isinstance(data, dict) or data.get("binding") != expected:
        return False
    return (
        _checked(data)
        and _metadata(data)
        and games(data.get("games"))
        and retained(data.get("retained"))
    )
