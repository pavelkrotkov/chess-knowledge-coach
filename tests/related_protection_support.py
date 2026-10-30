"""Synthetic owned protection and licensed-style local corpus fixtures."""

import chess

from tests.test_objective_protection import fixture, oriented

PRE = "4k3/7p/8/2b5/3R4/8/PP6/7K b - - 0 1"


def source_and_corpus(path, monkeypatch, *, black=False):
    db, evidence = fixture(path, monkeypatch, black=black)
    board = chess.Board(PRE)
    if black:
        board = board.mirror()
    lines = {
        "defense": ["h7h6", "d4d3", "e8f8", "d3d2"],
        "wrong": ["h7h6", "a2a3", "e8f8", "a3a4"],
    }
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    for key, line in lines.items():
        solution = " ".join(oriented(move, black) for move in line)
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid',?,1200,80,'["defensiveMove"]','unknown')""",
            (key, corpus, board.fen(), solution),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'defensiveMove',1200)", (corpus, key)
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence


def add_public(db):
    import json

    from chess_coach.puzzle_session_validate import validate_line

    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    pre = PRE.replace("PP6", "PPP5")
    prompt = validate_line(pre, "h7h6 d4d3 e8f8 d3d2")
    lines = ["a2a3 e8f8 a3a4", "d4d3 e8f8 d3d2"]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "fixture", prompt, "legal_line", json.dumps(lines)),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
