"""Arguments for bounded background-compatible processing."""


def configure(sub):
    parser = sub.add_parser("process-pipeline", help="Synchronize and process bounded pending work")
    parser.add_argument("username", nargs="?")
    parser.add_argument("--max-games", type=int, default=25)
    parser.add_argument("--max-scan", type=int, default=1000)
    parser.add_argument("--max-positions", type=int, default=300)
    parser.add_argument("--nodes", type=int, default=10000)
    parser.add_argument("--seconds-per-position", type=float, default=1.0)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--engine-path", default="/usr/games/stockfish")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--network-retries", type=int, default=1)
    parser.add_argument("--network-requests", type=int, default=50)
    parser.add_argument("--network-timeout", type=float, default=30.0)
    parser.add_argument("--network-seconds", type=float, default=120.0)
    parser.add_argument("--network-bytes", type=int, default=8388608)
    parser.add_argument("--network-sleep", type=float, default=60.0)
    parser.add_argument("--opening-version")
    parser.add_argument("--opening-source")
    parser.add_argument("--structure-version", default="0.1.0")
    parser.add_argument("--classifier-version", default="1.0.0")
    parser.add_argument("--ontology-version", default="tactical-mate-v1")
    parser.add_argument("--tactical-version", default="1.0.0")

    sub.add_parser("pipeline-status", help="Read durable processing status")
