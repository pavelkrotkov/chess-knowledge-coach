"""Explain only the checked mate threat and tested immediate defense."""

from .lesson_adapter_common import line


def describe(evidence, fen):
    fact = evidence.get("discovery_defense_observation") or {}
    if not fact.get("threat") or not fact.get("defense") or not fact.get("witness"):
        return [], []
    threat, defense, witness = fact["threat"], fact["defense"], fact["witness"]
    facts = [
        f"After the recorded move {fact['played']['san'][0]}, {threat['san']} reveals the slider on {threat['slider']} and checkmates.",
        f"The legal alternative {witness['san']} independently permits the same mate.",
        f"The tested defense {defense['san']} prevents every immediate opposing checkmate. Later consequences remain unknown.",
    ]
    return facts, [
        line(fen, "Recorded move and discovered mate", fact["played"]["san"][:2]),
        line(fen, "Tested immediate defense", [defense["san"]]),
    ]
