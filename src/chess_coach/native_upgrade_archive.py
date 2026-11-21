"""Verify archive contents without materializing another restore."""

import gzip
import hashlib
import zlib

from .native_upgrade_sink import Guard, Sink
from .recovery_zstd_frame import inspect
from .recovery_zstd_process import transform

CHUNK = 64 * 1024


def _gzip(archive, manifest, deadline):
    total = 0
    digest = hashlib.sha256()
    try:
        with gzip.open(archive, "rb") as stream:
            while chunk := stream.read(CHUNK):
                deadline.check()
                total += len(chunk)
                if total > manifest["raw_bytes"]:
                    raise ValueError("recovery archive exceeds snapshot")
                digest.update(chunk)
    except (EOFError, zlib.error):
        raise ValueError("recovery archive unavailable") from None
    return total, digest.hexdigest()


def _zstd(archive, manifest, deadline):
    inspect(archive, deadline)
    with archive.open("rb") as source:
        result = transform(
            source,
            Sink(),
            ["-q", "-d", "-M8MB", "-c"],
            manifest["archive_bytes"],
            manifest["raw_bytes"],
            Guard(deadline),
            deadline,
            restoring=True,
        )
    if result["input_sha256"] != manifest["archive_sha256"]:
        raise ValueError("recovery archive changed")
    return result["output_bytes"], result["output_sha256"]


def verify(archive, manifest, deadline, codec):
    decoder = {"gzip": _gzip, "zstd": _zstd}.get(codec)
    if decoder is None:
        raise ValueError("unsupported recovery codec")
    size, digest = decoder(archive, manifest, deadline)
    if size != manifest["raw_bytes"] or digest != manifest["raw_sha256"]:
        raise ValueError("recovery archive contents differ")
