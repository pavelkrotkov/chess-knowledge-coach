"""Validate a complete line and prove its first pin-defense-capture branch."""

from .pin_geometry import pins
from .related_pin_budget import take
from .related_pin_certificate import certified, same
from .related_pin_contract import PIN_GEOMETRY_LIMIT
from .related_pin_shape import features
from .related_pin_validate import root_and_move


def candidate_line(board, line, source, budget):
    if not take(budget, "lines"):
        return None
    try:
        root, move = root_and_move(board, line)
        return _candidate(root, move, line, source, budget)
    except (ValueError, TypeError, KeyError, IndexError):
        budget["unknown"] += 1
        return None


def _candidate(root, move, line, source, budget):
    geometry = pins(root, move)
    if len(geometry) > PIN_GEOMETRY_LIMIT:
        raise ValueError("pin geometry limit")
    if not _compatible(root, move, geometry, source):
        return None
    if not take(budget, "root_proofs"):
        return None
    result = certified(root, move, line, source)
    if result is None:
        budget["unknown"] += 1
    return result


def _compatible(board, move, geometry, source):
    return any(same(features(board, move, pin), source) for pin in geometry)
