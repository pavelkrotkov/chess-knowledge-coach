"""Validate exact selection against a reconstructed public chapter."""

import chess

from .opening_storage import position_key
from .opening_unfamiliar_lesson import lesson as public_lesson
from .opening_unfamiliar_selection import _valid


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


def validate_measurement(current):
    selection = current.get("selection")
    if not selection or len(current["chapters"]) != 1:
        raise ValueError("opening measurement differs")
    color = selection["color"]
    expected = public_lesson(
        current["report"], color, current["report"][color], current["measurement"]
    )
    if current["chapters"][0] != expected:
        raise ValueError("opening measurement differs")
