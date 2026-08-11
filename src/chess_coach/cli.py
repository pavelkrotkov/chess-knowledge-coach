from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .db import Database
from .evidence import evidence_report
from .ingest import ingest_pgn
from .lichess import LichessClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-first chess knowledge coach")
    parser.add_argument("--db", default="coach.sqlite", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    ingest = sub.add_parser("ingest-pgn")
    ingest.add_argument("path", type=Path)
    sync = sub.add_parser("sync-lichess", help="Import a user's Lichess game export")
    sync.add_argument("username")
    sync.add_argument("--max-games", type=int, default=100)
    sync.add_argument("--page-size", type=int, default=100)
    sync.add_argument("--since", type=int)
    sub.add_parser("evidence-report")
    args = parser.parse_args()
    db = Database(args.db)
    db.initialize()
    if args.command == "init-db":
        print(f"initialized {args.db}")
    elif args.command == "ingest-pgn":
        print(json.dumps(ingest_pgn(db, args.path.open()), indent=2))
    elif args.command == "sync-lichess":
        client = LichessClient(token=os.environ.get("LICHESS_API_TOKEN"))
        print(
            json.dumps(
                client.sync_user(
                    db,
                    args.username,
                    max_games=args.max_games,
                    page_size=args.page_size,
                    since=args.since,
                ),
                indent=2,
            )
        )
    elif args.command == "evidence-report":
        print(json.dumps(evidence_report(db), indent=2))


if __name__ == "__main__":
    main()
