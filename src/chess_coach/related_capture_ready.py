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


def score(window):
    prepared = {
        (
            entry["candidate"]["type"],
            entry["candidate"]["version"],
            entry["candidate"]["key"],
        ): entry
        for entry in (*window["entries"].values(), *window["public"]["entries"].values())
    }

    def candidate(item, source, seen, baseline):
        entry = prepared.get((item["type"], item["version"], item["key"]))
        field = "solution" if item["type"] == "corpus" else "line"
        if entry is None or any(entry["candidate"][key] != item[key] for key in ("fen", field)):
            raise ValueError("capture preparation changed")
        features = _features(entry)
        if features is None:
            return None
        prompt, line = _line(item)
        if certified_features(prompt, line) != features:
            raise ValueError("capture preparation changed")
        if not compatible(source, features):
            return None
        return _scored(item, source, features, prompt, prompt_key(prompt), baseline)

    return candidate


def _line(item):
    if item["type"] == "corpus":
        return validate_line(item["fen"], item["solution"]), item["solution"].split()[1:]
    return item["fen"], item["line"].split()
