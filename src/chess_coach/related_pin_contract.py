"""Version and bounded-work limits for pin transfer."""

VERSION = "pin-execution-transfer-v2"
FILTER_VERSION = "pin-execution-lines-v1"
PREVENT_VERSION = "pin-pinner-capture-transfer-v1"
PREVENT_FILTER_VERSION = "pin-pinner-capture-lines-v1"
CREATED_VERSION = "pin-counterfactual-transfer-v1"
CREATED_FILTER_VERSION = "pin-counterfactual-lines-v1"
SLIDE_VERSION = "pin-relative-slide-transfer-v1"
SLIDE_FILTER_VERSION = "pin-relative-slide-lines-v1"
ABSOLUTE_SLIDE_VERSION = "pin-absolute-slide-transfer-v1"
ABSOLUTE_SLIDE_FILTER_VERSION = "pin-absolute-slide-lines-v1"
LINE_LIMIT = 64
ROOT_PROOF_LIMIT = 64
PIN_GEOMETRY_LIMIT = 8
SOURCE_ROOT_PROOF_RESERVATION = 2


def filter_version(version):
    return {
        ABSOLUTE_SLIDE_VERSION: ABSOLUTE_SLIDE_FILTER_VERSION,
        SLIDE_VERSION: SLIDE_FILTER_VERSION,
        CREATED_VERSION: CREATED_FILTER_VERSION,
        PREVENT_VERSION: PREVENT_FILTER_VERSION,
    }.get(version, FILTER_VERSION)


def transfer_version(source):
    features = source["features"]
    if features.get("origin") == "slide":
        return ABSOLUTE_SLIDE_VERSION if features["pin_kind"] == "absolute_pin" else SLIDE_VERSION
    if features.get("origin") == "counterfactual":
        return CREATED_VERSION
    return PREVENT_VERSION if features.get("operation") == "prevent" else VERSION


def operation(version):
    return (
        "prevent"
        if version in {PREVENT_VERSION, CREATED_VERSION, SLIDE_VERSION, ABSOLUTE_SLIDE_VERSION}
        else "execute"
    )


class UnsupportedPinTransfer(ValueError):
    """The current owned source is outside the pinner-capture slice."""


def bound_filter(key, provenance, default):
    if key != "related_pin":
        return default
    if not isinstance(provenance, dict):
        raise ValueError("practice line selection unavailable")
    return filter_version(provenance.get("rank_version"))
