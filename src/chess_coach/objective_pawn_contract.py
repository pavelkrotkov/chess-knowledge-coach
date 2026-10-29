"""Versioned identities for an owned pawn-ending result objective."""

VERSION = "pawn-result-own-v1"
OBJECTIVE = "pawn-result-v1"
VERIFIER = "pawn-result-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] in {"preserve_pawn_win", "preserve_pawn_draw"}
    )
