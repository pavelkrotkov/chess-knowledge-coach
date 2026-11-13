"""Validate frozen proof versions and capture-certificate binding."""

from .mate_proof import VERSION as MATE_VERSION
from .objective_capture_judge import VERSION as CAPTURE_VERSION
from .related_capture_assessment import PROOF_VERSION
from .related_capture_assessment import VERSION as CAPTURE_ASSESSMENT


def proof(value):
    if value.get("kind") == "mate":
        return _mate(value)
    return _capture(value)


def _mate(value):
    if (value.get("capture_verifier"), value.get("mate_verifier"), value.get("history_mode")) != (
        CAPTURE_VERSION,
        MATE_VERSION,
        "zeroing_setup",
    ) or not _mate_fields(value.get("mate")):
        raise ValueError("recognition proof changed")


def _mate_fields(mate):
    return (
        isinstance(mate, dict)
        and isinstance(mate.get("san"), str)
        and isinstance(mate.get("uci"), str)
    )


def _capture(value):
    saved = value.get("proof")
    if not isinstance(saved, dict) or not isinstance(saved.get("proof"), dict):
        raise ValueError("recognition proof unavailable")
    expected = (
        "capture",
        CAPTURE_ASSESSMENT,
        PROOF_VERSION,
        "zeroing_setup",
        3,
        value.get("source_fingerprint"),
    )
    actual = (
        value.get("kind"),
        saved.get("version"),
        saved.get("proof_version"),
        saved.get("history_mode"),
        saved.get("gain_threshold"),
        saved.get("source_fingerprint"),
    )
    if actual != expected or not _capture_fields(saved):
        raise ValueError("recognition proof changed")


def _capture_fields(saved):
    detail = saved["proof"]
    return (
        detail.get("status") == "correct"
        and detail.get("verifier") == CAPTURE_VERSION
        and isinstance(detail.get("san"), str)
        and isinstance(saved.get("target"), str)
        and type(detail.get("proven_gain_floor")) is int
        and detail["proven_gain_floor"] >= 3
    )
