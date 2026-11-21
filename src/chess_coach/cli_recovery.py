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
    "backup-db": _backup,
    "restore-db": _restore,
    "backup-gzip-verify": _gzip,
    "restore-gzip": _restore_gzip,
    "backup-zstd-verify": _zstd,
    "restore-zstd": _restore_zstd,
}
