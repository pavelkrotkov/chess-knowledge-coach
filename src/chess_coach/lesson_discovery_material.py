"""Explain a source-checked recorded-choice material exposure."""

from .lesson_adapter_common import line


def describe(evidence, fen):
    fact = evidence.get("discovery_material_observation") or {}
    if not fact.get("threat") or not fact.get("defense"):
        return [], []
    threat, defense = fact["threat"], fact["defense"]
    facts = [
        f"After the recorded move {fact['played']['san'][0]}, the analyzed reply {threat['san']} reveals the slider on {threat['slider']} toward {threat['target']}.",
        f"Against each of {threat['legal_replies']} supported replies, a target capture proves at least {threat['minimum_gain']} material points.",
        f"The tested alternative {defense['san']} prevents that named discovery and every immediate opposing mate. The original threat's origin and other material threats remain unknown.",
    ]
    return facts, [
        line(fen, "Recorded choice and tested capture", fact["played"]["san"]),
        line(fen, "Tested alternative", fact["best"]["san"]),
    ]
