"""Accept only direct Lichess broadcast source links."""

import re
from urllib.parse import urlsplit

ROUND_PATH = r"/broadcast/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9]{8}"
PATH = re.compile(ROUND_PATH + r"(?:/[A-Za-z0-9]{8})?/?")
GAME_PATH = re.compile(ROUND_PATH + r"/[A-Za-z0-9]{8}/?")


def site(value):
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    if parts.scheme != "https" or parts.netloc != "lichess.org" or parts.query or parts.fragment:
        return ""
    return value if len(value) <= 500 and PATH.fullmatch(parts.path) else ""


def game_site(value):
    result = site(value)
    return result.rstrip("/") if result and GAME_PATH.fullmatch(urlsplit(result).path) else ""
