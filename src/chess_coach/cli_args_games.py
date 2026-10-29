"""Arguments for games commands."""

from pathlib import Path


def configure(sub):
    sub.add_parser("init-db")
    ingest = sub.add_parser("ingest-pgn")
    ingest.add_argument("path", type=Path)
    analyze = sub.add_parser("analyze-game")
    analyze.add_argument("game_id", type=int)
    analyze.add_argument("--engine-path", default="/usr/games/stockfish")
    analyze.add_argument("--nodes", type=int, default=20_000)
    analyze.add_argument("--depth", type=int)
    analyze.add_argument("--multipv", type=int, default=1)
    analyze.add_argument("--threads", type=int, default=1)
    analyze.add_argument("--hash", dest="hash_mb", type=int, default=64)
    inspect = sub.add_parser("inspect-decision", help="Inspect a same-board engine comparison")
    inspect.add_argument("position_id", type=int)
    inspect.add_argument("--run-id", type=int)
    mate = sub.add_parser("inspect-mate", help="Inspect bounded mate proof for an owned decision")
    mate.add_argument("position_id", type=int)
    mate.add_argument("--source-fingerprint")
    maia = sub.add_parser("predict-maia")
    maia.add_argument("position_id", type=int)
    maia.add_argument("--command", dest="maia_command")
    maia.add_argument("--model", default="maia-3")
    maia.add_argument("--checkpoint", required=True)
    sync = sub.add_parser("sync-lichess", help="Import a user's Lichess game export")
    sync.add_argument("username")
    sync.add_argument("--max-games", type=int, default=100)
    sync.add_argument("--page-size", type=int, default=100)
    sync.add_argument("--since", type=int)
