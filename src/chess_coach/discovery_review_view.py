"""Attach the source-checked discovery view to evidence details."""

from .discovery_defense_evidence import current as defense_current
from .discovery_evidence import current


def apply(db, evidence, *, _history=None):
    observation, state, fen = current(db, evidence, _history=_history)
    evidence["discovery_observation"] = observation
    evidence["discovery_currentness"] = state
    if state == "current":
        evidence["decision_fen"] = fen
    defense, defense_state, defense_fen = defense_current(db, evidence, _history=_history)
    evidence["discovery_defense_observation"] = defense
    evidence["discovery_defense_currentness"] = defense_state
    if defense_state == "current":
        evidence["decision_fen"] = defense_fen
