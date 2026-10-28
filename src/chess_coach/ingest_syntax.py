"""Reject move text that python-chess would silently ignore."""

from __future__ import annotations

import re

import chess.pgn

MOVE_NUMBER = re.compile(r"[0-9]+[.](?:[.][.])?")
SUFFIX = re.compile(r"[+#]+")


def next_token(text: str, start: int) -> int:
    character = text[start]
    if character.isspace() or character == chr(0xFEFF):
        return start + 1
    if character in "[;%":
        end = text.find(chr(10), start)
        return len(text) if end < 0 else end + 1
    if character == "{":
        end = text.find("}", start)
        if end < 0:
            raise ValueError("incomplete PGN comment")
        return end + 1
    return move_end(text, start)


def move_end(text: str, start: int) -> int:
    match = MOVE_NUMBER.match(text, start) or SUFFIX.match(text, start)
    if match is None:
        match = chess.pgn.MOVETEXT_REGEX.match(text, start)
    if match is None:
        raise ValueError("invalid PGN move text")
    return match.end()


def validate_syntax(text: str) -> None:
    offset = 0
    while offset < len(text):
        offset = next_token(text, offset)
