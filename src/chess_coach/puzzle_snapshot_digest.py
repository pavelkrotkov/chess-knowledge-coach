"""Hash archive bytes under the same resource deadline."""

import hashlib

from .puzzle_snapshot_budget import check_budget


def hash_file(path, limits, deadline):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            check_budget(path.parent, limits, deadline, 0, 0)
            digest.update(chunk)
    return digest


def digest_file(path, limits, deadline):
    return hash_file(path, limits, deadline).hexdigest()


def partial_hash(archive, offset, state, limits, deadline):
    digest = hash_file(archive, limits, deadline) if offset else hashlib.sha256()
    if offset and digest.hexdigest() != state.get("partial_sha256"):
        raise ValueError("partial archive hash differs from checkpoint")
    return digest
