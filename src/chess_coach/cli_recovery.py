"""Recovery commands that never initialize the source database."""

import json
from pathlib import Path

from .recovery import backup_database, restore_database
from .recovery_gzip import compressed_recovery
from .recovery_gzip_single import restore_backup


def configure(sub):
    parser = sub.add_parser("plan-analysis-history")
    parser.add_argument("source", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)

    for name in ("backup-db", "restore-db", "restore-gzip", "restore-zstd"):
        parser = sub.add_parser(name)
        parser.add_argument("source", type=Path)
        parser.add_argument("destination", type=Path)
        parser.add_argument("--project-root", type=Path, required=True)
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="estimate space without creating a destination",
        )

    for name in ("backup-gzip-verify", "backup-zstd-verify"):
        parser = sub.add_parser(name)
        parser.add_argument("source", type=Path)
        parser.add_argument("archive", type=Path)
        parser.add_argument("restored", type=Path)
        parser.add_argument("--project-root", type=Path, required=True)
        parser.add_argument("--check-only", action="store_true")

    parser = sub.add_parser("offline-gzip-pair")
    for name in ("source", "archive_a", "archive_b", "restored"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--acknowledge-source-unlink", action="store_true", required=True)

    parser = sub.add_parser("restore-offline-gzip-pair")
    for name in ("archive_a", "archive_b", "metadata", "restored"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--project-root", type=Path, required=True)


def _offline_pair(args):
    from .recovery_pair import offline_pair

    result = offline_pair(
        args.source,
        args.archive_a,
        args.archive_b,
        args.restored,
        project_root=args.project_root,
        acknowledge_unlink=args.acknowledge_source_unlink,
    )
    print(json.dumps(result))


def _restore_pair(args):
    from .recovery_pair import manual_restore

    result = manual_restore(
        args.archive_a, args.archive_b, args.metadata, args.restored, project_root=args.project_root
    )
    print(json.dumps(result))


def _compressed(args, codec):
    result = compressed_recovery(
        args.source,
        args.archive,
        args.restored,
        project_root=args.project_root,
        check_only=args.check_only,
        codec=codec,
    )
    print(json.dumps(result))


def _gzip(args):
    _compressed(args, "gzip")


def _zstd(args):
    _compressed(args, "zstd")


def _restore_gzip(args):
    result = restore_backup(
        args.source, args.destination, project_root=args.project_root, check_only=args.check_only
    )
    print(json.dumps(result))


def _restore_zstd(args):
    result = restore_backup(
        args.source,
        args.destination,
        project_root=args.project_root,
        check_only=args.check_only,
        codec="zstd",
    )
    print(json.dumps(result))


def _backup(args):
    result = backup_database(
        args.source, args.destination, project_root=args.project_root, check_only=args.check_only
    )
    print(json.dumps(result if args.check_only else {"status": "verified"}))


def _restore(args):
    result = restore_database(
        args.source, args.destination, project_root=args.project_root, check_only=args.check_only
    )
    print(json.dumps(result if args.check_only else {"status": "verified"}))


def _plan_analysis_history(args):
    from .analysis_history_plan import plan

    print(json.dumps(plan(args.source, args.project_root)))


COMMANDS = {
    "plan-analysis-history": _plan_analysis_history,
    "offline-gzip-pair": _offline_pair,
    "restore-offline-gzip-pair": _restore_pair,
    "backup-db": _backup,
    "restore-db": _restore,
    "backup-gzip-verify": _gzip,
    "restore-gzip": _restore_gzip,
    "backup-zstd-verify": _zstd,
    "restore-zstd": _restore_zstd,
}
