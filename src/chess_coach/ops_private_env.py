"""Limit subprocess environment and collect values to redact."""

import os
from urllib.parse import unquote, urlsplit

PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
SAFE_ENV = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)
PRIVATE_ENV = (
    "USER",
    "LOGNAME",
    "HOME",
    "CHESS_SUBJECT",
    "CHESS_REVIEW_ACTOR",
    "CHESS_TAILSCALE_LOGIN",
    "LICHESS_USERNAME",
    "LICHESS_API_TOKEN",
    "CHESS_WEB_ORIGIN",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def environment_and_secrets() -> tuple[dict[str, str], list[bytes]]:
    environment = {name: value for name in SAFE_ENV if (value := os.environ.get(name)) is not None}
    secrets = [value.encode() for name in PRIVATE_ENV if (value := os.environ.get(name))]
    for name in PROXY_ENV:
        secrets.extend(_proxy_secrets(os.environ.get(name)))
    return environment, secrets


def _proxy_secrets(value: str | None) -> list[bytes]:
    if not value:
        return []
    try:
        parsed = urlsplit(value)
        parts = (parsed.username, parsed.password)
    except ValueError:
        return []
    return [item.encode() for part in parts if part for item in (part, unquote(part))]
