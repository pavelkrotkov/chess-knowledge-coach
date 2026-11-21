"""Contrast only two current, independently qualified protection responses."""

from .style_guard_inspect import VERSION


def classify(pair):
    played = pair["played"].get("protection")
    alternative = pair["alternative"].get("protection")
    if played is None and alternative is None:
        return None
    left = (played or {}).get("exchange")
    right = (alternative or {}).get("exchange")
    if left is None or right is None:
        return "ambiguous"
    # Both roots must share the exact current source and qualified contract.
    if not _same_source(left, right):
        return "ambiguous"
    return _contrast(left, right)


def _contrast(left, right):
    left_guard, right_guard = bool(left.get("guard_witness")), bool(right.get("guard_witness"))
    if left_guard == right_guard:
        return None
    contrast = _alternative(right if left_guard else left)
    return ("guarded" if left_guard else contrast) if contrast else None


def eligible(pair):
    left = pair["played"].get("protection", {}).get("exchange")
    right = pair["alternative"].get("protection", {}).get("exchange")
    return left is not None and right is not None and _same_source(left, right)


def _alternative(result):
    if result.get("moved_target"):
        return "moved_target"
    if result.get("captured_attacker"):
        return "captured_attacker"
    return None


def _same_source(left, right):
    return (
        left.get("status") == right.get("status") == "supported"
        and left.get("version") == right.get("version") == VERSION
        and left.get("evidence_id") == right.get("evidence_id") is not None
        and left.get("source_target") == right.get("source_target") is not None
        and left.get("source") == right.get("source") is not None
    )
