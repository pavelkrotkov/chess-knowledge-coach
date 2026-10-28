"""Find the last mainline PGN token while ignoring comments and variations."""

from .ingest_syntax import next_token


def _meaningful(token: str) -> bool:
    return not (token.isspace() or token[0] in "[;{%" or token == chr(0xFEFF))


def last_mainline_token(text: str) -> str | None:
    offset = 0
    variation_depth = 0
    last = None
    while offset < len(text):
        end = next_token(text, offset)
        token = text[offset:end]
        if token == "(":
            variation_depth += 1
        elif token == ")":
            variation_depth = max(0, variation_depth - 1)
        elif not variation_depth and _meaningful(token):
            last = token
        offset = end
    return last
