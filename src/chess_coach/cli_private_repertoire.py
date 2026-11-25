"""Run explicitly selected repertoire reports without initializing the database."""

import json


def run(args):
    if args.command != "repertoire":
        return False
    if args.fork_nominations or args.revision_judgments:
        if args.unfamiliar_contexts or (args.fork_nominations and args.revision_judgments):
            raise ValueError("select one repertoire mode")
        from .opening_fork_nomination_cli import report
    elif args.unfamiliar_contexts:
        from .opening_context_cli import report
    else:
        return False
    options = {"revision": True} if args.revision_judgments else {}
    print(json.dumps(report(args.project_root, args.learner, args.db, **options), indent=2))
    return True
