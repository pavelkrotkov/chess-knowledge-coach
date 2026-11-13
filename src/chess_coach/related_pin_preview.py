"""Describe the exact bounded pin-transfer source and coverage."""

from . import related_pin_contract as contract


def _source(result, chosen):
    version = contract.transfer_version(chosen[0])
    if contract.operation(version) != "prevent":
        return
    result["operation"] = "prevent"
    result["pin_kind"] = chosen[0]["features"]["pin_kind"]
    if chosen[0]["features"].get("origin") == "slide":
        result["pin_origin"] = "slide"
    if chosen[0]["features"].get("origin") == "counterfactual":
        result["pin_origin"] = "counterfactual"


def _text(result):
    if result.get("pin_origin") == "slide" and result["pin_kind"] == "absolute_pin":
        return (
            "The named checking capture has a supported legal reply that leaves less than "
            "three immediate material points. Other threats, compensation and later play remain unknown."
        )
    if result.get("pin_origin") == "slide":
        return (
            "The owned exposure and supplied slide are rechecked. The named rear capture "
            "is blocked; other threats, compensation and later play remain unknown."
        )
    if result.get("pin_origin") == "counterfactual":
        return (
            "The owned contrast and candidate lines are independently checked with bounded "
            "pin proofs. Earlier pin consequences and later safety remain unknown."
        )
    if result.get("operation") == "prevent":
        return (
            "The owned source is rechecked with its recorded history and a legal pinner "
            "capture proof. Candidate lines are independently replayed and checked."
        )
    return (
        "Source currentness uses up to two pin-root rechecks with at most eight pin "
        "geometries each. History and material work are separate; limits are not a deadline."
    )


def details(result, chosen):
    _source(result, chosen)
    result["pin_scan"] = chosen[2]["pin_scan"]
    result["source_verification"] = _text(result)
    if result["pin_scan"]["truncated"]:
        result["status"] = "partial: candidate proof budget exhausted"
