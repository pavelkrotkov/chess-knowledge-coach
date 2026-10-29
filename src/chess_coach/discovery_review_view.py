"""Attach the source-checked discovery view to evidence details."""

from .discovery_evidence import current


def apply(db, evidence, *, _history=None):
    observation, state, fen = current(db, evidence, _history=_history)
    evidence["discovery_observation"] = observation
    evidence["discovery_currentness"] = state
    if state == "current":
        evidence["decision_fen"] = fen
