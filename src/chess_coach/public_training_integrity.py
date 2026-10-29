"""Verify both source and normalized content throughout collection import."""

import hashlib

from .puzzle_import_source import unchanged


def verify_snapshot(paths, signatures, manifest):
    for path, expected in zip(paths, signatures, strict=True):
        unchanged(path, expected)
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    if hashes != [manifest["content_sha256"], manifest["source_sha256"]]:
        raise ValueError("collection checksum mismatch")
    for path, expected in zip(paths, signatures, strict=True):
        unchanged(path, expected)
