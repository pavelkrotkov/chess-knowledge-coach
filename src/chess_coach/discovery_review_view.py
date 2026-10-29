"""Attach the source-checked discovery view to evidence details."""

from .discovery_evidence import current


def apply(db, evidence):
    observation, state, fen = current(db, evidence)
    evidence["discovery_observation"] = observation
    evidence["discovery_currentness"] = state
    if state == "current":
        evidence["decision_fen"] = fen
