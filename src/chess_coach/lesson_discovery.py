"""Describe only the recorded, source-rechecked discovery witness."""

from .lesson_adapter_common import line, valid_square
from .lesson_lines import legal_san


def describe(evidence, fen):
    fact = evidence.get("discovery_observation") or {}
    proof = fact.get("proof") or {}
    move, slider, target = proof.get("san"), proof.get("slider"), proof.get("target")
    if not legal_san(fen, [move]) or not valid_square(slider) or not valid_square(target):
        return [], []
    return _facts(fact, proof, move, slider, target), [_witness_line(fen, move, proof)]


def _facts(fact, proof, move, slider, target):
    origin = "The tested alternative" if fact.get("outcome") == "failure" else "The played move"
    facts = [f"{origin} {move} uncovers the slider on {slider} toward {target}."]
    if proof.get("double_check"):
        facts.append("The move gives double check.")
    if proof.get("mate"):
        facts.append("The move is checkmate.")
    return facts


def _witness_line(fen, move, proof):
    if proof.get("mate"):
        return line(fen, "Proved mate", [move])
    return _sample_line(fen, move, proof)


def _sample_line(fen, move, proof):
    sample = next(iter(proof.get("branches") or []), {})
    return line(
        fen,
        "One tested defense and capture",
        [move, sample.get("reply_san"), sample.get("capture_san")],
    )
