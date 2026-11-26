"""Rebind and copy a prepared capture assessment for admission."""

from .related_capture_pool import complete
from .related_capture_ready import _features, entries


def assessment(db, version, key, source, baseline, corpus):
    from .related_capture_assessment import setup
    from .related_capture_assessment_context import capture

    window = complete(db, db.capture_root, version, corpus["lower"], corpus["upper"])
    if window is None:
        raise ValueError("capture preparation pending")
    entry = entries(window).get(key)
    if entry is None or entry.get("assessment") is None:
        raise ValueError("capture assessment unavailable")
    _, _, fingerprint = setup(db, version, key)
    result = dict(entry["assessment"])
    if result.get("source_fingerprint") != fingerprint:
        raise ValueError("capture assessment changed")
    try:
        result["context"] = capture(
            db, version, key, source, baseline, corpus, feature=_features(entry)
        )
    except (ValueError, TypeError, KeyError):
        result["context"] = None
    return result


def legacy_assessment(db, version, key, selected):
    from .related_capture_assessment import certificate
    from .related_capture_assessment_context import capture

    result = certificate(db, version, key)
    try:
        result["context"] = capture(db, version, key, *selected[:3])
    except (ValueError, TypeError, KeyError):
        result["context"] = None
    return result


def attach(db, source_type, version, key, binding, selected, secret):
    if secret is None or source_type != "corpus":
        raise ValueError("capture assessment unavailable")
    binding["assessment"] = assessment(db, version, key, *selected[:3])
