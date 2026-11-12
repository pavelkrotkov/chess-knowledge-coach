"""Match current protection roles and a bounded public difficulty band."""

import chess

BAND = 200


def context(db, version, key, binding, prompt, line):
    row = db.connection.execute(
        """SELECT p.rating FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        (version, key),
    ).fetchone()
    if row is None or type(row["rating"]) is not int or not 0 <= row["rating"] < 4000:
        raise ValueError("protection difficulty unavailable")
    board = chess.Board(prompt)
    move = board.parse_uci(line.split()[0])
    target = chess.parse_square(binding["objective_target"])
    mover, victim = board.piece_type_at(move.from_square), board.piece_type_at(target)
    if mover is None or victim is None or move not in board.legal_moves:
        raise ValueError("protection role unavailable")
    return (mover, victim, binding["protection_mechanism"], row["rating"] // BAND)


def candidate(db, item):
    if item["type"] != "corpus":
        raise ValueError("protection corpus required")
    return context(db, item["version"], item["key"], item, item["fen"], item["matching_lines"][0])
