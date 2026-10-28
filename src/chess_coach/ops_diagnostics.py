"""Bound and sanitize private diagnostics for release preparation."""

import os
import subprocess
from pathlib import Path

MAX_DIAGNOSTIC_BYTES = 65536


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    release: Path,
    stage: str,
    secrets: list[bytes],
) -> None:
    try:
        process = subprocess.Popen(
            command, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
    except OSError as exc:
        _fail(release, stage, str(exc).encode(), secrets, False, None)
    output, truncated = _read_output(process)
    status = process.wait()
    if status != 0:
        _fail(release, stage, output, secrets, truncated, status)


def _read_output(process: subprocess.Popen) -> tuple[bytes, bool]:
    assert process.stdout is not None
    output = bytearray()
    truncated = False
    with process.stdout:
        while chunk := process.stdout.read(8192):
            room = MAX_DIAGNOSTIC_BYTES - len(output)
            output.extend(chunk[:room])
            truncated |= len(chunk) > room
    return bytes(output), truncated


def _fail(
    release: Path,
    stage: str,
    output: bytes,
    secrets: list[bytes],
    truncated: bool,
    status: int | None,
) -> None:
    safe = _redact(output, secrets, truncated)
    path = release / "prepare-error.log"
    relative = f".runtime/releases/{release.name}/prepare-error.log"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(f"{stage} failed (status: {status})\n".encode() + safe)
    except OSError:
        raise RuntimeError(
            f"{stage} failed; could not create private diagnostics at {relative}"
        ) from None
    raise RuntimeError(f"{stage} failed; see {relative}") from None


def _redact(output: bytes, secrets: list[bytes], truncated: bool) -> bytes:
    # A secret crossing the truncation boundary must not expose its prefix.
    if truncated and secrets:
        longest = max(map(len, secrets))
        output = output[: max(0, len(output) - longest + 1)]
    for value in sorted(set(secrets), key=len, reverse=True):
        output = output.replace(value, b"[redacted]")
    if len(output) > MAX_DIAGNOSTIC_BYTES:
        output = output[:MAX_DIAGNOSTIC_BYTES]
        truncated = True
    if truncated:
        output += b"\n[output truncated]\n"
    return output
