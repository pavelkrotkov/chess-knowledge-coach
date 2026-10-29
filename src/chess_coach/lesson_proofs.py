"""Pawn and mate lesson facts from bounded proofs."""

from .lesson_adapter_common import line


def _pawn(evidence, fen):
    note = evidence.get("pawn_explanation") or {}
    lines = [line(fen, "Result-preserving choice", [move]) for move in note.get("preserving", [])]
    if not any(lines):
        return [], []
    result = {1: "win", 0: "draw", -1: "loss"}.get(note.get("root"))
    outcome = note.get("outcome")
    facts = ["The bounded pawn proof found a legal choice that preserves the position result."]
    if result and outcome in {"success", "failure", "ambiguous"}:
        facts.append(
            f"The proved position result was {result}; the recorded choice was classified {outcome}."
        )
    return facts, lines[:3]


def _mate_outcome(observation):
    if observation.get("immediate_mate_not_played"):
        return "An immediate mate was available and the recorded move did not deliver it."
    if observation.get("played_checkmate"):
        return "The recorded move delivered checkmate."
    return None


def _mate(evidence, fen):
    observation = evidence["facts"][0]["payload"]
    proof = observation.get("proof") or {}
    roots = [root for root in proof.get("alternatives", []) if root.get("status") == "proved"]
    lines = [
        line(fen, "Proved mating choice", [(root.get("move") or {}).get("san")]) for root in roots
    ]
    if not any(lines):
        return [], []
    facts = ["A bounded proof found a forced mating choice."]
    outcome = _mate_outcome(observation)
    if outcome:
        facts.append(outcome)
    return facts, lines[:3]
