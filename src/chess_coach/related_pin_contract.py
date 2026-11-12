"""Version and bounded-work limits for pin transfer."""

VERSION = "pin-execution-transfer-v2"
FILTER_VERSION = "pin-execution-lines-v1"
PREVENT_VERSION = "pin-pinner-capture-transfer-v1"
PREVENT_FILTER_VERSION = "pin-pinner-capture-lines-v1"
LINE_LIMIT = 64
ROOT_PROOF_LIMIT = 64
PIN_GEOMETRY_LIMIT = 8
SOURCE_ROOT_PROOF_RESERVATION = 2


def filter_version(version):
    return PREVENT_FILTER_VERSION if version == PREVENT_VERSION else FILTER_VERSION


def transfer_version(source):
    return PREVENT_VERSION if source["features"].get("operation") == "prevent" else VERSION


def operation(version):
    return "prevent" if version == PREVENT_VERSION else "execute"


class UnsupportedPinTransfer(ValueError):
    """The current owned source is outside the pinner-capture slice."""


def bound_filter(key, provenance, default):
    if key != "related_pin":
        return default
    if not isinstance(provenance, dict):
        raise ValueError("practice line selection unavailable")
    return filter_version(provenance.get("rank_version"))
