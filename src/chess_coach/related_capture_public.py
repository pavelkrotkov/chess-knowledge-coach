"""Bound licensed public task inspection and preserve collection versions."""

from urllib.parse import urlparse

from .public_training_query import collections, tasks
from .unified_sources import resolve_source

PUBLIC_SCAN = 500


def public_candidates(db, familiar_games, *, all_lines=False):
    result, metadata, scanned = [], [], 0
    for collection in collections(db):
        metadata.append(
            [
                collection[k]
                for k in (
                    "version",
                    "source_revision",
                    "source_sha256",
                    "content_sha256",
                    "accepted",
                )
            ]
        )
        if scanned >= PUBLIC_SCAN or _game_id(collection["source_url"]) in familiar_games:
            continue
        for item in tasks(db, collection["version"], limit=min(100, PUBLIC_SCAN - scanned)):
            scanned += 1
            try:
                resolved = resolve_source(db, "public", collection["version"], item["task_id"])
            except ValueError:
                continue
            result.append(
                {
                    "type": "public",
                    "version": collection["version"],
                    "key": item["task_id"],
                    "fen": resolved["prompt_fen"],
                    **(
                        {"lines": resolved["lines"]}
                        if all_lines
                        else {"line": resolved["lines"][0]}
                    ),
                }
            )
    return result, {"versions": metadata, "scanned": scanned}


def _game_id(source):
    parsed = urlparse(source)
    if parsed.hostname not in {"lichess.org", "www.lichess.org"}:
        return None
    return parsed.path.strip("/").split("/")[0]
