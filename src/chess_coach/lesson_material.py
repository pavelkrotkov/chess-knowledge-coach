"""Describe the tested material target and continuations."""

from .lesson_adapter_common import line as checked_line
from .lesson_adapter_common import valid_square
from .material_explanation import explain_material


def _material(evidence, fen):
    note = explain_material({"material_observation": evidence["facts"][0]["payload"]}) or {}
    facts = [note["summary"]] if note.get("summary") else []
    piece, square = note.get("piece"), note.get("target")
    if piece in {"pawn", "knight", "bishop", "rook", "queen"} and valid_square(square):
        facts.append(f"The tested target was the {piece} on {square}.")
    lines = [checked_line(fen, "Recorded best-search continuation", note.get("best"))]
    lines.append(checked_line(fen, "Recorded played-search continuation", note.get("played")))
    return facts, lines
