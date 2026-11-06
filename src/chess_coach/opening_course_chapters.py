"""Build the private owned and attributed public course chapters."""

from .course_pgn import chapter
from .opening_experiment_export import pgn as owned_pgn
from .opening_reference_source import LICENSE, LICENSE_URL, SOURCE, SOURCE_ARCHIVE, SOURCE_SHA256


def owned(decision, choice, experiment):
    return {
        "kind": "owned",
        "title": "Your worked comparison",
        "pgn": owned_pgn(decision, choice, experiment),
    }


def public(example):
    link = example["site"] or SOURCE_ARCHIVE
    note = (
        f"Observed public continuation from {link}. "
        f"Source: Lichess broadcasts, {SOURCE}; license: {LICENSE}, {LICENSE_URL}. "
        f"Choose {example['san'][0]}; after {example['san'][1]}, "
        "find your continuation before revealing the line. "
        "This example describes recorded play; preparation and soundness remain unknown."
    )
    snapshot = {
        "prompt_fen": example["fen"],
        "learner_color": example["color"],
        "lines": [" ".join(example["moves"])],
    }
    result = chapter("Public opening continuation", note, snapshot, {}, guidance=note)
    return {
        "kind": "public",
        "title": "Public continuation",
        "reference": example["reference"],
        "pgn": result["pgn"],
        "source": link,
        "direct": bool(example["site"]),
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "archive_sha256": SOURCE_SHA256,
        "san": example["san"],
    }
