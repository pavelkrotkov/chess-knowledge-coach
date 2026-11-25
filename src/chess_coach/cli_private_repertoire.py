"""Run explicitly selected repertoire reports without initializing the database."""

import json


def _report(args):
    modes = (args.unfamiliar_contexts, args.fork_nominations, args.revision_judgments)
    if sum(modes) > 1:
        raise ValueError("select one repertoire mode")
    if args.unfamiliar_contexts:
        from .opening_context_cli import report

        return report
    if args.fork_nominations or args.revision_judgments:
        from .opening_fork_nomination_cli import report

        return report
    return None


def run(args):
    if args.command != "repertoire":
        return False
    report = _report(args)
    if report is None:
        return False
    options = {"revision": True} if args.revision_judgments else {}
    print(json.dumps(report(args.project_root, args.learner, args.db, **options), indent=2))
    return True
