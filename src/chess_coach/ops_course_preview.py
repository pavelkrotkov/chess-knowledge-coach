"""Prepare a private course without initializing the live database."""

import argparse
import json
import os
from pathlib import Path

from .course_current import build_readonly
from .course_paths import paths


def prepare(root, preview_path, output):
    database, _, preview_path, output = paths(root, preview_path, output, output=True)
    with preview_path.open(encoding="utf-8") as handle:
        envelope = json.load(handle)
    result = build_readonly(database, envelope)
    encoded = json.dumps(result, sort_keys=True, allow_nan=False).encode()
    descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return result["course_sha256"]


def main():
    parser = argparse.ArgumentParser(description="Prepare a private course preview")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare(args.project_root, args.preview, args.output)
    except Exception:
        raise SystemExit("Course preview unavailable; no provider data was written.") from None
    print("Private course preview prepared and validated.")


if __name__ == "__main__":
    main()
