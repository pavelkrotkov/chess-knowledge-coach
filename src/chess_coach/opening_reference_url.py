"""Accept only direct Lichess broadcast source links."""

from urllib.parse import urlsplit


def site(value):
    parts = urlsplit(value)
    allowed = parts.scheme == "https" and parts.netloc == "lichess.org"
    if allowed and parts.path.startswith("/broadcast/") and not (parts.query or parts.fragment):
        return value if len(value) <= 500 else ""
    return ""
