"""Require a single complete, checksummed Zstandard frame."""

from .recovery_zstd_native import run


def inspect(archive, deadline):
    with archive.open("rb") as stream:
        header = stream.read(5)
    if len(header) != 5 or header[:4] != bytes.fromhex("28b52ffd") or not header[4] & 4:
        raise ValueError("Zstandard checksum frame required")
    info = run(["-lv", str(archive)], deadline).splitlines()
    if "# Zstandard Frames: 1" not in info or not any(
        line.startswith("Check: XXH64 ") for line in info
    ):
        raise ValueError("single checksummed Zstandard frame required")
