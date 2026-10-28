"""Revalidate a selected recommendation before creating a session."""

from flask import current_app

from .curriculum import daily_plan
from .db import Database


def recommended(db: Database, version: str, puzzle_id: str, cursor: str | None) -> bool:
    try:
        result = daily_plan(
            db,
            subject=current_app.config["SUBJECT"],
            corpus_version=current_app.config["CORPUS"],
            cursor=cursor,
        )
    except ValueError:
        return False
    return any(
        item["corpus_version"] == version and item["puzzle_id"] == puzzle_id
        for item in result["items"]
    )
