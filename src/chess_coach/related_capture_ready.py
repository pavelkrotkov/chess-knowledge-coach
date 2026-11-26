"""Rebind prepared corpus entries without running admission proofs."""

from .puzzle_session_validate import validate_line
from .related_capture_features import certified_features
from .related_capture_match import _scored
from .related_capture_position import compatible, prompt_key


def _features(entry):
    features = entry.get("feature")
    if features is None:
        return None
    return {
        **features,
        "geometry": tuple(features["geometry"]),
        "material": tuple(features["material"]),
    }


def entries(window):
    return {entry["candidate"]["key"]: entry for entry in window["entries"].values()}


def score(window, public_pending):
    prepared = entries(window)

    def candidate(item, source, seen, baseline):
        if item["type"] != "corpus":
            features = certified_features(item["fen"], item["line"].split())
            public_pending[0] |= compatible(source, features)
            return None
        entry = prepared.get(item["key"])
        if entry is None or any(
            entry["candidate"][key] != item[key] for key in ("version", "fen", "solution")
        ):
            raise ValueError("capture preparation changed")
        features = _features(entry)
        if features is None:
            return None
        prompt = validate_line(item["fen"], item["solution"])
        checked = certified_features(prompt, item["solution"].split()[1:])
        if checked != features:
            raise ValueError("capture preparation changed")
        if not compatible(source, features):
            return None
        prompt_id = prompt_key(prompt)
        return _scored(item, source, features, prompt, prompt_id, baseline)

    return candidate
