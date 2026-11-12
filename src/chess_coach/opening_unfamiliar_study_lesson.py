"""Check exact public opening chapter identity, line and attribution."""

from .opening_study_chapter import chapter, line
from .opening_unfamiliar_binding import binding


def _binding(report, color, value):
    item = report[color]
    source, snapshot = value["source"], value["source_snapshot"]
    expected = item["line"]
    source_snapshot, provenance = binding(report, color, item)
    if any(
        (
            value["mode"] != "conceal",
            value["orientation"] != color,
            value["color"] != color,
            source != provenance,
            snapshot != source_snapshot,
        )
    ):
        raise ValueError("unfamiliar opening chapter differs")
    return expected


def _line(value, color, expected):
    _checked, game = chapter(value, color, expected["fen"])
    nodes = list(game.mainline())
    if any(
        (
            len(nodes) != 4,
            not line(game, " ".join(expected["moves"])),
            any(len(node.variations) != 1 for node in [game, *nodes[:-1]]),
            " ".join(game.comment.split()) != " ".join(value["note"].split()),
        )
    ):
        raise ValueError("unfamiliar opening line differs")
    return game


def lesson(report, color, value):
    expected = _binding(report, color, value)
    game = _line(value, color, expected)
    source = value["source"]
    if not all(
        str(source[key]) in game.comment
        for key in ("source_url", "license", "license_url", "archive_sha256", "catalog_source")
    ):
        raise ValueError("unfamiliar opening attribution differs")
    return value
