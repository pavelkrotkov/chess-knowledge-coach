"""Explicitly publish a reviewed course while respecting the existing sync lock."""

import argparse
import json
from pathlib import Path

from .course_paths import paths
from .study_session import publish_locked


def run(root, preview, course):
    database, planning, preview, course = paths(root, preview, course, output=False)
    with preview.open(encoding="utf-8") as handle:
        envelope = json.load(handle)
    with course.open(encoding="utf-8") as handle:
        frozen = json.load(handle)
    return publish_locked(database, planning, envelope, frozen)


def main():
    parser = argparse.ArgumentParser(description="Publish one reviewed private Study")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--course", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(run(args.project_root, args.preview, args.course))
    except Exception:
        raise SystemExit(
            "Publication incomplete; retain the private intent for reconciliation."
        ) from None


if __name__ == "__main__":
    main()
