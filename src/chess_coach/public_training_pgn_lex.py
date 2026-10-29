"""Require complete lexical consumption of bounded PGN game text."""

import re

from .public_training_pgn_state import accept_token

TOKEN = re.compile(
    r"""
    (?P<space>\s+)
  | (?P<tag>^\[[^\r\n]*\][ \t]*(?:\r?\n|$))
  | (?P<comment>\{[^}]*\}|;[^\r\n]*|^%[^\r\n]*)
  | (?P<number>\d+\.(?:\.\.)?)
  | (?P<result>1/2-1/2|1-0|0-1|\*)
  | (?P<san>(?:[NBKRQ]?[a-h]?[1-8]?[\-x]?[a-h][1-8](?:=?[nbrqkNBRQK])?
             |[PNBRQK]?@[a-h][1-8]|--|Z0|0000|@@@@|O-O(?:-O)?|0-0(?:-0)?)[+#]?)
  | (?P<nag>\$[0-9]+|[?!]{1,2})
  | (?P<open>\()
  | (?P<close>\))
""",
    re.VERBOSE | re.MULTILINE,
)


def valid_movetext(text):
    """Reject ignored characters, malformed tags, and unbalanced variations."""
    text = text.removeprefix("\ufeff")
    state = {"moves": [0], "result": False, "started": False}
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if match is None or not accept_token(match, text, state):
            return False
        position = match.end()
    return len(state["moves"]) == 1
