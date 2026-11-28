"""Report a private opening profile without initializing the database."""

import json
import os

from .opening_profile_cli_args import parse as parse_arguments
from .opening_profile_cli_report import preparation, prepare_public, report


def main():
    args = parse_arguments()
    try:
        arguments = (
            args.project_root,
            os.environ["CHESS_SUBJECT"],
            args.game_id,
            args.position_id,
            args.alternative,
        )
        if args.prepare_public:
            if args.reference != "recent":
                raise ValueError("recent reference required")
            value = prepare_public(
                *arguments,
                forks=args.prepare_public == "fork",
                fork_window=args.fork_window,
                prevent=args.prepare_public == "prevention",
                protection=args.prepare_public == "protection",
                capture_pv=args.prepare_public == "capture_pv",
                defense_pv=args.prepare_public == "defense_pv",
                mate=args.proof_kind == "mate",
                short_mate=args.proof_kind == "short_mate",
                back_rank=args.proof_kind == "back_rank",
                skewer=args.proof_kind == "skewer",
                double_mate=args.proof_kind == "double_mate",
            )
        elif args.recommendation_course:
            from .opening_recommendation_cli import report as recommendation

            value = recommendation(*arguments)
        elif args.preparation:
            value = preparation(*arguments)
        else:
            value = report(
                *arguments, args.reference, fork_window=args.fork_window, proof_kind=args.proof_kind
            )
    except Exception:
        raise SystemExit("Opening profile unavailable.") from None
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
