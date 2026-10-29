"""Stable identifiers for provisional material facts and mappings."""

PRODUCER = "material-opportunity"
VERSION = "1.0.0"
SCOPE = "material-v1"

CAPTURE_VERSION = "1.1.0"


def detector_version(fact):
    return VERSION if fact and fact.get("kind") == "material_protection" else CAPTURE_VERSION
