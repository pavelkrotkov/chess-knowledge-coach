"""Pinned and integrity-checked Lichess CC0 opening names."""

import hashlib
from pathlib import Path

from .opening_rows import _rows
from .openings import import_rows

VERSION = "e76b8b4ec5c8aeeba41dac6caf4a60b938f652db"
SOURCE = f"https://github.com/lichess-org/chess-openings/tree/{VERSION}"
CHECKSUMS = {
    "a": "3282e4c9155289a29224f9a85fba0decb46efa35c2fa5e39662d2ac48fb0f793",
    "b": "4bf2269a8e7571a00a7b346bae4fa86a241a6e7e86beab01783c81acb1622b63",
    "c": "45e843c7b7e79a0d04d5bda879c9bd23f5a10974488bd8615e4f4c5d0749986f",
    "d": "1cf4057a8aece94f27bb3f278ad410ee2844831a642364eeceaafa091dbcceda",
    "e": "48c6f6645b031a5937c8386839debab0e2e48837251687ba1afb6369677f8546",
}


def import_snapshot(db):
    """Verify all files before making one atomic import."""
    directory = Path(__file__).parent / "data" / "openings"
    paths = [directory / f"{letter}.tsv" for letter in CHECKSUMS]
    for path, expected in zip(paths, CHECKSUMS.values(), strict=True):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"opening snapshot checksum mismatch: {path.name}")
    rows = [row for path in paths for row in _rows(path)]
    return import_rows(db, rows, version=VERSION, source_url=SOURCE)
