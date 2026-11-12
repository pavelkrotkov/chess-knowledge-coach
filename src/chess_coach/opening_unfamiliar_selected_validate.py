"""Validate exact selection against a reconstructed public chapter."""

import chess

from .opening_storage import position_key
from .opening_unfamiliar_selected import _valid


def validate_content(current):
    selection = current["selection"]
    if not _valid(selection):
        raise ValueError("opening selection differs")
    colors = [color for color in ("white", "black") if current["report"][color]]
    if colors != [selection["color"]]:
        raise ValueError("opening selection differs")
    item = current["report"][selection["color"]]
    if any(
        (
            item["uci"] != selection["move"],
            item["line"]["moves"][0] != selection["move"],
            position_key(chess.Board(item["line"]["fen"])) != selection["parent"],
        )
    ):
        raise ValueError("opening selection differs")
