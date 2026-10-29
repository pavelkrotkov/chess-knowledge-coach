"""Verify the pinned, locally bundled Syzygy WDL subset before opening it."""

import hashlib
import json
from pathlib import Path

import chess.syzygy

MANIFEST_SHA256 = "fb200598ce8fb0231c70035bc1a3f7808e13bd207691baae0c9f8b1d46be8759"
DIRECTORY = Path(__file__).parent / "data" / "pawn_wdl"


def _verified(path, info):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != info["bytes"]:
        return False
    with path.open("rb") as stream:
        data = stream.read(info["bytes"] + 1)
    return (
        len(data) == info["bytes"]
        and len(data) % 64 == 16
        and hashlib.sha256(data).hexdigest() == info["sha256"]
        and data[-16:].hex() == info["embedded"]
    )


def open_verified(directory=DIRECTORY):
    """Return an open tablebase, or None if any required resource is unavailable."""
    try:
        with (directory / "manifest.json").open("rb") as stream:
            raw = stream.read(4097)
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            return None
        manifest = json.loads(raw)
        if not all(_verified(directory / name, info) for name, info in manifest.items()):
            return None
        # add_directory would accept unverified extra tables; add only allowlisted files.
        tablebase = chess.syzygy.Tablebase(max_fds=4)
        for name in manifest:
            tablebase.add_file(str(directory / name))
        return tablebase
    except (OSError, ValueError, TypeError, KeyError):
        return None
