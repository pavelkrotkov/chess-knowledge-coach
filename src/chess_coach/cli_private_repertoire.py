"""Run explicitly selected repertoire reports without initializing the database."""

import json


def run(args):
    if args.command != "repertoire":
        return False
    if args.fork_nominations:
        if args.unfamiliar_contexts:
            raise ValueError("select one repertoire mode")
        from .opening_fork_nomination_cli import report
    elif args.unfamiliar_contexts:
        from .opening_context_cli import report
    else:
        return False
    print(json.dumps(report(args.project_root, args.learner, args.db), indent=2))
    return True
