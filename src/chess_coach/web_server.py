"""Run the private browser application behind Tailscale Serve."""

import os
from pathlib import Path

from waitress import serve

from .db import Database
from .web import create_app
from .web_paths import inside, socket_directory, socket_location
from .web_socket import browser_socket


def main() -> None:
    root = Path(os.environ["CHESS_PROJECT_ROOT"]).resolve(strict=True)
    db_path = inside(root, os.environ["CHESS_DB"], existing=True)
    socket = socket_location(root, os.environ["CHESS_WEB_SOCKET"])
    socket_directory(socket)
    app = create_app(
        db_path=db_path,
        subject=os.environ["CHESS_SUBJECT"],
        actor=os.environ["CHESS_REVIEW_ACTOR"],
        corpus=os.environ["CHESS_CORPUS"],
        login=os.environ["CHESS_TAILSCALE_LOGIN"],
        origin=os.environ["CHESS_WEB_ORIGIN"],
    )
    db = Database(db_path)
    try:
        db.initialize()
    finally:
        db.close()
    with browser_socket(socket):
        serve(app, unix_socket=str(socket), unix_socket_perms="600", max_request_body_size=16384)


if __name__ == "__main__":
    main()
