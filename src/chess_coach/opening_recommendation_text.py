"""Add bounded evidence and uncertainty to one chosen worked line."""

import io

import chess.pgn


def provenance(label, source):
    return "{}: {}; license: {} ({}); preparation version: {}.".format(
        label,
        source["example"]["source"],
        source["reference"]["license"],
        source["reference"]["license_url"],
        source["version"],
    )


def note(choice, item, report):
    judgments = report["revision_judgments"]
    nomination = report["fork_nomination"]
    source = nomination["source"]
    fit = item.get("fit", {}).get("status", "unknown").replace("_", " ")
    development = item.get("development", {}).get("status", "unknown")
    history = item.get("preparation", {}).get("history", {})
    unseen = history.get("not_seen_edges")
    count = "unknown" if unseen is None else str(unseen)
    alternatives = ", ".join(
        "{}: {}".format(row["choice"]["san"], row["admission"]["status"])
        for row in judgments["alternatives"]
    )
    san = choice["san"]
    details = "Nominal control: {}. ".format(nomination["nominal_control"])
    details += provenance("Public example after the recorded branch", source)
    selected_source = item.get("development", {}).get("source")
    if selected_source:
        details += " " + provenance(
            "Public example after the selected alternative", selected_source
        )
    return (
        f"Selected by the learner: {san}. Conditional fit: {fit}; "
        f"fork-development evidence: {development}. Preparation edges not seen in the checked "
        f"sample: {count}. Compared alternatives: {alternatives}. These bounded observations "
        "do not establish opening causation, personal preference, or mastery. Unchecked work "
        "remains unknown; a provisional example is a learning experiment, not a diagnosis. "
        "Current all-root admission uses the existing 50 centipawn bounds. " + details
    )


def annotate(chapter, text):
    game = chess.pgn.read_game(io.StringIO(chapter["pgn"]))
    if game is None or game.errors:
        raise ValueError("opening course unavailable")
    game.comment = f"{game.comment} {text}".strip()
    return {**chapter, "pgn": str(game)}
