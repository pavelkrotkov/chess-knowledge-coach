"""Watch exact context artifacts, indexes and exposure inputs."""

from itertools import chain, islice
from pathlib import Path

from .opening_context_fork_binding import key as fork_key
from .opening_fit_context_index import INDEX_NAME as CONTEXT_INDEX
from .opening_profile_index import INDEX_NAME
from .opening_public_comparison_read import key as comparison_key
from .opening_public_proof_files import ATTEMPTS, _path, latest
from .tactical_study_intents import MAX_INTENTS
from .tactical_study_path import planning


def paths(root, subject, parent):
    directory, _ = planning(root, subject)
    config = Path(root) / ".runtime" / "config.env"
    result = [
        directory,
        directory / INDEX_NAME,
        directory / CONTEXT_INDEX,
        config,
        config.resolve(),
    ]
    for item in parent["items"]:
        selection = item["selection"]
        for key in (comparison_key(selection), fork_key(selection)):
            result.extend(_path(directory, key, attempt) for attempt in range(ATTEMPTS))
        payload = latest(directory, comparison_key(selection))
        if payload is not None:
            try:
                engine = Path(payload["configuration"]["engine_path"])
            except (KeyError, TypeError):
                raise ValueError("public engine unavailable") from None
            result.extend((engine, engine.resolve()))
    result.extend(_intents(directory))
    return result


def _intents(directory):
    paths = list(
        islice(
            chain(
                directory.glob("tactical-study-*-intent.json"),
                directory.glob("opening-study-*-intent.json"),
            ),
            MAX_INTENTS + 1,
        )
    )
    if len(paths) > MAX_INTENTS:
        raise ValueError("exposure inputs unavailable")
    return [*sorted(paths), directory / "poc-study-336-intent.json"]
