"""Explain the played defense and distinct legal mate witness."""

from .lesson_adapter_common import line


def describe(evidence, fen):
    fact = evidence.get("discovery_success_observation") or {}
    if not fact.get("threat") or not fact.get("witness") or not fact.get("played"):
        return [], []
    threat, witness, played = fact["threat"], fact["witness"], fact["played"]
    facts = [
        f"The played move {played['san']} prevents every immediate opposing checkmate.",
        f"The distinct legal alternative {witness['san']} permits {threat['san']}, revealing the slider on {threat['slider']} and checkmating.",
        "The opponent-turn geometry was a nomination. The alternative line was replayed with the original history. Later play and intent remain unknown.",
    ]
    return facts, [
        line(fen, "Played immediate defense", [played["san"]]),
        line(fen, "Distinct alternative and proved mate", [witness["san"], threat["san"]]),
    ]
