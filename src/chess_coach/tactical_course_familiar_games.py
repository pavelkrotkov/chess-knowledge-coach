"""Page owned game starts without scanning unrelated PGN content."""

from .related_capture_familiar import LIMIT, _initial_prompt

PAGE = 32


class FamiliarityLimit(ValueError):
    """The bounded familiarity history cannot be completed."""


def _pages(db, budget, table, fields, params=()):
    last = None
    while True:
        where = "" if last is None else "WHERE rowid > ?"
        values = params + ((PAGE,) if last is None else (last, PAGE))
        with budget.scope(snapshot=True):
            rows = db.connection.execute(
                f"SELECT rowid AS page_key,{fields} FROM {table} {where} ORDER BY rowid LIMIT ?",
                values,
            ).fetchall()
        if not rows:
            return
        yield rows
        last = rows[-1]["page_key"]


def _games(db, identity, budget):
    prompts, ids, count = set(), set(), 0
    fields = (
        "CASE WHEN lower(white)=? OR lower(black)=? THEN pgn END AS pgn,"
        "CASE WHEN lower(white)=? OR lower(black)=? THEN source_id END AS source_id"
    )
    for rows in _pages(db, budget, "games", fields, (identity,) * 4):
        with budget.scope(snapshot=False):
            for row in rows:
                if row["pgn"] is None:
                    continue
                count += 1
                if count > LIMIT:
                    raise FamiliarityLimit("familiarity scan limit exceeded")
                prompts.add(_initial_prompt(row["pgn"]))
                if row["source_id"]:
                    ids.add(row["source_id"])
    return prompts, ids
