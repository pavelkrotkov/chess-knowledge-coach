"""Describe a rechecked pin observation with legal source lines."""

from .lesson_adapter_common import line, valid_square
from .lesson_pin_capture import exposure
from .lesson_pin_creation import created


def pin(evidence, fen):
    note = evidence.get("pin_explanation") or {}
    proof = note.get("proof") or {}
    if proof.get("mode") in {"exposure", "pinned_capture"}:
        return exposure(evidence, note, fen)
    if proof.get("san"):
        return created(evidence, note, fen)
    return _geometry(evidence, note, fen)


def _geometry(evidence, note, fen):
    geometry = note.get("geometry") or {}
    if not valid_square(geometry.get("pinned")) or not valid_square(geometry.get("rear")):
        return [], []
    prefix = (
        [evidence["lesson_played_san"]] if geometry.get("origin") == "opponent_candidate" else []
    )
    tested = line(fen, "Unresolved pin geometry", [*prefix, geometry.get("san")])
    if not tested:
        return [], []
    san, pinned, rear = geometry["san"], geometry["pinned"], geometry["rear"]
    return [
        f"The tested move {san} pins the piece on {pinned} against {rear}; its consequence is unresolved."
    ], [tested]
