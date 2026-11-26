"""Command-line access to the read-only daily curriculum."""

import json

from .curriculum import daily_plan


def handle_daily_plan(db, args):
    print(
        json.dumps(
            daily_plan(
                db,
                subject=args.subject,
                corpus_version=args.version,
                limit=args.limit,
                scan_limit=args.scan_limit,
                cursor=args.cursor,
                goal=getattr(args, "goal", None),
                duration_minutes=getattr(args, "minutes", None),
                renew=getattr(args, "renew", False),
                project_root=getattr(args, "project_root", None),
            ),
            indent=2,
        )
    )
