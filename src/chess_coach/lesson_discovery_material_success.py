"""Explain an independently witnessed material defense."""

from .lesson_adapter_common import line


def describe(evidence, fen):
    fact = evidence.get("discovery_material_success_observation") or {}
    if not fact.get("threat") or not fact.get("witness") or not fact.get("played"):
        return [], []
    threat, witness, played = fact["threat"], fact["witness"], fact["played"]
    if not threat.get("branches"):
        return [], []
    branch = threat["branches"][0]
    example = [witness["san"], threat["san"], branch["reply_san"], branch["capture_san"]]
    facts = [
        f"The played move {played['san']} stops the named discovery and leaves the same target without an immediate legal capture.",
        f"The distinct legal alternative {witness['san']} permits {threat['san']}, revealing the slider on {threat['slider']} toward {threat['target']}. All {threat['legal_replies']} legal replies were checked.",
        f"One example reply is {branch['reply_san']}, followed by {branch['capture_san']}. The checked capture and immediate replies retain a gain of at least {threat['minimum_gain']} pawn units relative to the position before the discovery.",
        "The played move also prevents every immediate opposing checkmate. Other threats, later play and intent remain unknown.",
    ]
    return facts, [
        line(fen, "Played defense", [played["san"]]),
        line(fen, "Distinct alternative and example reply", example),
    ]
