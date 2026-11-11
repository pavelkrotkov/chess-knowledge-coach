"""Compare Lichess replays without changing stored source material."""

import re

HEADERS = re.compile(r"\A(?:[ \t]*\[[^\r\n]*\][ \t]*(?:\r?\n|$))+")
PLAYER = re.compile(r'(?m)^([ \t]*\[(?:White|Black)[ \t]+")([A-Za-z0-9_-]+)("\][ \t]*\r?$)')


def matches(stored: str, raw: str, source: str) -> bool:
    return stored == raw or (source == "lichess" and _canonical(stored) == _canonical(raw))


def _canonical(raw: str) -> str:
    headers = HEADERS.match(raw)
    if headers is None:
        return raw
    normalized = PLAYER.sub(lambda match: match[1] + match[2].lower() + match[3], headers[0])
    return normalized + raw[headers.end() :]
