"""Enumerate the bounded sidecars that can affect a revision judgment."""

from .fact_fingerprint import canonical, digest
from .opening_full_history_build import INDEX_NAME as FULL_INDEX
from .opening_public_fork_later import bound as full_bound
from .opening_public_proof_files import ATTEMPTS
from .opening_public_proof_files import _path as proof_path
from .opening_public_proof_versions import combined, continuation
from .opening_queue_binding import identity
from .opening_queue_location import location
from .opening_recent_source import INDEX_NAME, MANIFEST_NAME, PREFIX_NAME
from .opening_recommendation_binding import bindings
from .opening_recommendation_queue_paths import paths as queue_paths
from .opening_study_source import inputs as study_inputs


def _proof_paths(directory, base, sha):
    identities = [base, combined(base)]
    if sha is not None:
        identities.append(continuation(base, sha))
    return [
        proof_path(directory, digest(canonical(value)), attempt)
        for value in identities
        for attempt in range(ATTEMPTS)
    ]


def inputs(db, root, learner, decision, budget):
    choices = decision["catalog"]["items"]
    if not 1 <= len(choices) <= 8:
        raise ValueError("opening choices unavailable")
    directory, database = location(db, root, learner)
    source, config, base = bindings(
        db, root, learner, decision, database, choices[0]["uci"], budget
    )
    try:
        sha = full_bound(root, learner, budget.expires)[1]
    except (OSError, ValueError, TypeError, KeyError):
        sha = None
    paths = study_inputs(directory, identity(database, source, config), root)
    paths.extend(directory / name for name in (INDEX_NAME, MANIFEST_NAME, PREFIX_NAME, FULL_INDEX))
    for choice in choices:
        budget.check()
        selected = {**source, "alternative": choice["uci"], "child": choice["child"]}
        paths.extend(queue_paths(directory, database, selected, config))
        paths.extend(_proof_paths(directory, {**base, "source": selected}, sha))
    return paths
