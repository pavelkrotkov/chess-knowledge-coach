"""Describe the current mate-search corpus and stable source scope."""

import json

from .fact_fingerprint import canonical, digest
from .related_mate import selection
from .related_mate_search_scan import scan
from .related_mate_search_token import VERSION, seen, within_limit


def corpus_info(db, version, rating):
    row = db.connection.execute(
        """SELECT c.id,c.checksum,i.selection_json FROM puzzle_corpora c
        LEFT JOIN puzzle_imports i ON i.corpus_id=c.id
        WHERE c.version=? AND c.state='ready'""",
        (version,),
    ).fetchone()
    if row is None:
        raise ValueError("search corpus unavailable")
    lower, upper = (max(0, rating - 500), min(3999, rating + 500)) if rating else (600, 2200)
    return {
        "id": row["id"],
        "checksum": row["checksum"],
        "selection": json.loads(row["selection_json"]) if row["selection_json"] else None,
        "lower": lower,
        "upper": upper,
        "public": {"scanned": 0},
    }


def root(subject, version, source, rating, corpus):
    return digest(
        canonical(
            [
                VERSION,
                subject,
                version,
                source,
                rating,
                corpus["checksum"],
                corpus["selection"],
                corpus["lower"],
                corpus["upper"],
            ]
        )
    )


def seed(db, subject, evidence, version, secret):
    chosen = selection(db, subject, evidence, version)
    if chosen is None or chosen[0]["objective"] != "mate_within_two":
        raise ValueError("short-mate search unavailable")
    source, rating, _, ordered, _, _ = chosen
    corpus = corpus_info(db, version, rating)
    prompts, games = seen(secret, ordered)
    if not within_limit(prompts, games):
        return None
    _, keys, _ = scan(db, version, corpus, [0] * 5, set(), secret)
    return {
        "version": VERSION,
        "root": root(subject, version, source, rating, corpus),
        "keys": keys,
        "prompts": prompts,
        "games": games,
        "offset": 0,
        "scope": None,
    }
