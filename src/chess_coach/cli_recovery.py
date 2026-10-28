"""Recovery commands that never initialize the source database."""

import json
from pathlib import Path

from .recovery import backup_database, restore_database


def configure(sub):
    for name in ("backup-db", "restore-db"):
        parser = sub.add_parser(name)
        parser.add_argument("source", type=Path)
        parser.add_argument("destination", type=Path)
        parser.add_argument("--project-root", type=Path, required=True)


def _backup(args):
    backup_database(args.source, args.destination, project_root=args.project_root)
    print(json.dumps({"status": "verified"}))


def _restore(args):
    restore_database(args.source, args.destination, project_root=args.project_root)
    print(json.dumps({"status": "verified"}))


COMMANDS = {"backup-db": _backup, "restore-db": _restore}
