"""Score compatible supplied-line captures on visible prompt context."""

from .related_capture_features import capture_features, corpus_features
from .related_capture_position import compatible, prompt_key, similarity


def candidate(candidate, source, seen, baseline):
    prompt, features = _prompt(candidate)
    if not prompt or not compatible(source, features):
        return None
    key = prompt_key(prompt)
    if key in seen:
        return None
    return _scored(candidate, source, features, prompt, key, baseline)


def _scored(candidate, source, features, prompt, key, baseline):
    shared = similarity(source, features)
    opening = candidate.get("opening") or ""
    shared_opening = bool(source.get("opening") and source["opening"] in opening.split())
    rating = candidate.get("rating")
    distance = (
        abs(rating - (baseline if baseline is not None else 1400)) if rating is not None else 4000
    )
    deviation = candidate.get("rating_deviation") if rating is not None else None
    return {
        "type": candidate["type"],
        "version": candidate["version"],
        "key": candidate["key"],
        "fen": prompt,
        "prompt_key": key,
        "game": candidate.get("game"),
        "diversity": (
            candidate["type"],
            features["phase"],
            features["geometry"],
            features["material"],
        ),
        "rating": rating,
        "rating_deviation": candidate.get("rating_deviation"),
        "shared_phase": features["phase"] if shared[1] else None,
        "same_material": shared[2] == 0,
        "shared_opening": shared_opening,
        "order": (
            -shared[0],
            -shared[1],
            -shared[2],
            -int(shared_opening),
            distance,
            deviation if deviation is not None else 4000,
            candidate["type"],
            candidate["version"],
            candidate["key"],
        ),
    }


def _prompt(candidate):
    if candidate["type"] == "corpus":
        return corpus_features(candidate["fen"], candidate["solution"])
    prompt = candidate["fen"]
    return prompt, capture_features(prompt, candidate["line"].split())
