"""Explain an independently witnessed material defense."""

from .lesson_adapter_common import line


def describe(evidence, fen):
    fact = evidence.get("discovery_material_success_observation") or {}
    if not fact.get("threat") or not fact.get("witness") or not fact.get("played"):
        return [], []
    threat, witness, played = fact["threat"], fact["witness"], fact["played"]
    facts = [
        f"The played move {played['san']} stops the named discovery and leaves the same target without an immediate legal capture.",
        f"The distinct legal alternative {witness['san']} permits {threat['san']}, revealing the slider on {threat['slider']} toward {threat['target']}. All {threat['legal_replies']} legal replies were checked.",
        "The played move also prevents every immediate opposing checkmate. Other threats, later play and intent remain unknown.",
    ]
    return facts, [
        line(fen, "Played defense", [played["san"]]),
        line(fen, "Distinct alternative and proved discovery", [witness["san"], threat["san"]]),
    ]
