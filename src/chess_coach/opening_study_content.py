"""Rebuild the original owned and public opening Study chapters."""

from .opening_revision_roles import VERSION, version
from .opening_study_chapter import chapter, line


def content(current, chapters):
    if current["schema"] == VERSION and (
        version(current["source_version"], current["chapters"]) != current["version"]
    ):
        raise ValueError("opening preview version differs")
    decision = current["decision"]
    color, fen = decision["color"], decision["fen"]
    owned_value, public_value = chapters
    owned, game = chapter(owned_value, color, fen)
    public, reference = chapter(public_value, color, fen, exact=False)
    experiment = current["experiment"]
    if len(game.variations) != 2 or not all(
        line(game, experiment[branch]["uci"]) for branch in ("played", "alternative")
    ):
        raise ValueError("opening variations differ")
    if not all(
        str(public_value[key]) in reference.comment for key in ("source", "license", "license_url")
    ):
        raise ValueError("public attribution differs")
    return [owned, public]
