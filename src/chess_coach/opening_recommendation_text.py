"""Add bounded evidence and uncertainty to one chosen worked line."""

import io

import chess.pgn


def note(choice, item, report):
    fit = item.get("fit", {}).get("status", "unknown").replace("_", " ")
    development = item.get("development", {}).get("status", "unknown")
    history = item.get("preparation", {}).get("history", {})
    unseen = history.get("not_seen_edges")
    count = "unknown" if unseen is None else str(unseen)
    alternatives = ", ".join(
        "{}: {}".format(row["choice"]["san"], row["admission"]["status"])
        for row in report["alternatives"]
    )
    san = choice["san"]
    return (
        f"Selected by the learner: {san}. Conditional fit: {fit}; "
        f"fork-development evidence: {development}. Preparation edges not seen in the checked "
        f"sample: {count}. Compared alternatives: {alternatives}. These bounded observations "
        "do not establish opening causation, personal preference, or mastery. Unchecked work "
        "remains unknown; a provisional example is a learning experiment, not a diagnosis."
    )


def annotate(chapter, text):
    game = chess.pgn.read_game(io.StringIO(chapter["pgn"]))
    if game is None or game.errors:
        raise ValueError("opening course unavailable")
    game.comment = f"{game.comment} {text}".strip()
    return {**chapter, "pgn": str(game)}
