"""Validate bounded, project-local licensed collection provenance."""

import json
from pathlib import Path

from .public_training_integrity import verify_snapshot
from .public_training_license import validate_manifest
from .puzzle_import_source import signature


def read_manifest(path, root, content, source):
    root = Path(root).resolve(strict=True)
    paths = [inside(item, root) for item in (path, content, source)]
    if paths[0].stat().st_size > 16384 or paths[1].stat().st_size > 5_000_000:
        raise ValueError("collection input exceeds size limit")
    if paths[2].stat().st_size > 5_000_000:
        raise ValueError("source input exceeds size limit")
    try:
        manifest = json.loads(paths[0].read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("invalid collection manifest") from None
    validate_manifest(manifest)
    signatures = [signature(item) for item in paths[1:]]
    verify_snapshot(paths[1:], signatures, manifest)
    return manifest, paths[1], paths[2], signatures


def inside(path, root):
    candidate = Path(path).resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError("collection input must be a project-local file")
    return candidate
