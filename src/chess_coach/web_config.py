"""Validate the browser identity and trusted origin."""

from urllib.parse import urlsplit


def validate_config(subject: str, actor: str, corpus: str, login: str, origin: str) -> str:
    if not all(
        isinstance(value, str) and value.strip() for value in (subject, actor, corpus, login)
    ):
        raise ValueError("browser identity and corpus configuration are required")
    parsed = urlsplit(origin)
    if not _valid_origin(parsed):
        raise ValueError("browser origin must be an exact HTTPS origin")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("browser origin cannot contain credentials")
    return parsed.netloc


def _valid_origin(parsed) -> bool:
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
    )
