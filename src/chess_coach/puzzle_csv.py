"""Read Lichess puzzle streams and convert rows for storage."""

from __future__ import annotations

import csv
import hashlib
import subprocess
from itertools import chain
from pathlib import Path
from typing import TextIO, cast

_FIELDS = [
    "PuzzleId",
    "FEN",
    "Moves",
    "Rating",
    "RatingDeviation",
    "Popularity",
    "NbPlays",
    "Themes",
    "GameUrl",
    "OpeningTags",
]


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_csv(path: Path) -> tuple[TextIO, subprocess.Popen[str] | None]:
    if path.suffix == ".zst":
        try:
            process = subprocess.Popen(
                ["zstd", "--decompress", "--stdout", str(path)],
                stdout=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(f"zstd command not found or failed to start: {exc}") from exc
        if process.stdout is None:
            raise RuntimeError("zstd did not provide a readable stream")
        return cast(TextIO, process.stdout), process
    return path.open(encoding="utf-8", newline=""), None


def _reader(stream: TextIO) -> csv.DictReader[str]:
    first = stream.readline()
    if not first:
        return csv.DictReader([], fieldnames=_FIELDS)
    lines = chain([first], stream)
    if first.split(",", 1)[0].strip() == "PuzzleId":
        return csv.DictReader(lines)
    return csv.DictReader(lines, fieldnames=_FIELDS)
