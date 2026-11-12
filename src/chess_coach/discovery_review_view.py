"""Attach the source-checked discovery view to evidence details."""

from .discovery_defense_evidence import current as defense_current
from .discovery_evidence import current
from .discovery_mate_success_evidence import current as success_current
from .discovery_material_evidence import current as material_current
from .discovery_material_success_evidence import current as material_success_current


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
    material, material_state, material_fen = material_current(db, evidence, _history=_history)
    evidence["discovery_material_observation"] = material
    evidence["discovery_material_currentness"] = material_state
    if material_state == "current":
        evidence["decision_fen"] = material_fen
    success, success_state, success_fen = success_current(db, evidence, _history=_history)
    evidence["discovery_success_observation"] = success
    evidence["discovery_success_currentness"] = success_state
    if success_state == "current":
        evidence["decision_fen"] = success_fen
    material_success, state, fen = material_success_current(db, evidence, _history=_history)
    evidence["discovery_material_success_observation"] = material_success
    evidence["discovery_material_success_currentness"] = state
    if state == "current":
        evidence["decision_fen"] = fen
