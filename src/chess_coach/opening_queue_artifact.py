"""Validate one bounded immutable opening measurement envelope."""

from .fact_fingerprint import canonical, digest
from .opening_queue_files import read


def path(directory, item):
    return directory / f"opening-comparison-{item['id']}-{item['attempt']}.json"


def load(directory, item):
    envelope = read(path(directory, item))
    if envelope is None:
        return None
    if not isinstance(envelope, dict) or not isinstance(envelope.get("measurement"), dict):
        raise ValueError("comparison result unavailable")
    return _checked(envelope, item)


def _checked(envelope, item):
    payload = envelope["measurement"]
    if envelope.get("sha256") != digest(canonical(payload)):
        raise ValueError("comparison result unavailable")
    if payload.get("version") != "opening-catalog-measurement-v1":
        raise ValueError("comparison version differs")
    if (
        payload.get("source") != item["source"]
        or payload.get("configuration") != item["configuration"]
    ):
        raise ValueError("comparison result differs")
    outcome = payload.get("result")
    if not isinstance(outcome, dict) or outcome.get("status") not in ("complete", "insufficient"):
        raise ValueError("comparison result unavailable")
    return payload
