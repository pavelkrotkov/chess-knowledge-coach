"""Validate the small persisted opening request slot."""

from .opening_queue_binding import VERSION, identity


def valid(value, database):
    if not isinstance(value, dict) or value.get("version") != VERSION:
        return False
    if value.get("database") != database or value.get("state") not in ("queued", "unavailable"):
        return False
    return _valid_content(value, database)


def _valid_content(value, database):
    attempt = value.get("attempt")
    if type(attempt) is not int or not 0 <= attempt < 3:
        return False
    source, config = value.get("source"), value.get("configuration")
    if not isinstance(source, dict) or not isinstance(config, dict):
        return False
    return value.get("id") == identity(database, source, config)
