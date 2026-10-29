"""Operator and read-only public collection commands."""

import json
from pathlib import Path

from .public_training import import_collection
from .public_training_query import collections, task, tasks


def configure(sub):
    add = sub.add_parser("import-public-training")
    add.add_argument("content", type=Path)
    add.add_argument("--source", required=True, type=Path)
    add.add_argument("--manifest", required=True, type=Path)
    add.add_argument("--project-root", required=True, type=Path)
    listing = sub.add_parser("list-public-training")
    listing.add_argument("--after-version", default="")
    show = sub.add_parser("show-public-training")
    show.add_argument("--version", required=True)
    show.add_argument("--limit", type=int, default=100)
    show.add_argument("--after-id", default="")
    show.add_argument("--task-id")


def handle_import(db, args):
    print(
        json.dumps(
            import_collection(
                db, args.content, args.source, args.manifest, project_root=args.project_root
            ),
            indent=2,
        )
    )


def handle_list(db, args):
    print(json.dumps(collections(db, args.after_version), indent=2))


def handle_show(db, args):
    result = (
        task(db, args.version, args.task_id)
        if args.task_id
        else tasks(db, args.version, args.limit, args.after_id)
    )
    print(json.dumps(result, indent=2))
