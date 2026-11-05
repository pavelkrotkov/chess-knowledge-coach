"""Publish one explicit verified tactical export to its private Study."""

import argparse
from pathlib import Path

from .tactical_course_deadline import PreviewDeadline
from .tactical_study_session import publish_locked


def main():
    parser = argparse.ArgumentParser(description="Publish a verified private tactical Study")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--export-sha256", required=True)
    args = parser.parse_args()
    try:
        publish_locked(args.project_root, args.export, args.export_sha256)
    except (Exception, PreviewDeadline):
        raise SystemExit(
            "Tactical Study publication incomplete; retain the private intent."
        ) from None
    print("Private tactical Study verified.")


if __name__ == "__main__":
    main()
