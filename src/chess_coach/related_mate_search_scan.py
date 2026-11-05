"""Seek bounded mate candidates independently in five rating bands."""

from .related_capture_candidates import _corpus, _game_id
from .related_mate_search_anchor import position
from .related_mate_search_token import fingerprint

BATCH = 100


def _band(db, corpus, index, key, secret):
    if key is None:
        return [], None
    lower, upper = corpus["lower"], corpus["upper"]
    width = max(1, (upper - lower + 1) // 5)
    start = lower + index * width
    end = upper if index == 4 else start + width - 1
    seek = position(db, corpus, key, start, end, secret)
    rows = db.connection.execute(
        """SELECT p.*,t.rowid AS anchor_id,t.rating AS indexed_rating FROM puzzle_themes t
        INDEXED BY idx_puzzle_themes_search JOIN puzzles p
        ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
        WHERE t.corpus_id=? AND t.theme='mateIn2'
        AND (t.rating,t.puzzle_id)>(?,?) AND t.rating<=?
        ORDER BY t.rating,t.puzzle_id LIMIT ?""",
        (corpus["id"], *seek, end, BATCH + 1),
    ).fetchall()
    last = rows[BATCH - 1] if len(rows) > BATCH else None
    if last is None:
        return rows[:BATCH], None
    anchor = [last["anchor_id"], last["indexed_rating"], last["puzzle_id"]]
    return rows[:BATCH], [anchor[0], fingerprint(secret, "anchor", anchor)]


def scan(db, version, corpus, keys, familiar_games, secret):
    pool, next_keys, examined = [], [], 0
    for index, key in enumerate(keys):
        rows, following = _band(db, corpus, index, key, secret)
        next_keys.append(following)
        examined += len(rows)
        pool.extend(
            _corpus(row, version) for row in rows if _game_id(row["source"]) not in familiar_games
        )
    return pool, next_keys, examined
