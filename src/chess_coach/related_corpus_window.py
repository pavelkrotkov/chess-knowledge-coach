"""Read an indexed, bounded slice of each corpus rating band."""


def band(lower, upper, index):
    width = max(1, (upper - lower + 1) // 5)
    start = lower + index * width
    return start, upper if index == 4 else start + width - 1


def corpus_rows(db, corpus_id, lower, upper, theme, per_band):
    rows, limited = [], False
    for index in range(5):
        start, stop = band(lower, upper, index)
        batch = db.connection.execute(
            """SELECT p.* FROM puzzle_themes t JOIN puzzles p ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
            WHERE t.corpus_id=? AND t.theme=? AND t.rating BETWEEN ? AND ?
            ORDER BY t.rating,t.puzzle_id LIMIT ?""",
            (corpus_id, theme, start, stop, per_band + 1),
        ).fetchall()
        limited |= len(batch) > per_band
        rows.extend(batch[:per_band])
    return rows, limited
