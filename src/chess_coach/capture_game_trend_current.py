"""Check cached dates and visible source links without replaying games."""

from .capture_game_trend_validate import matches_frontier


def _dates(candidates, games):
    starts = {game["id"]: game["projected_start"] for game, _ in candidates}
    return all(starts.get(item["id"]) == item["date"] for item in games)


def _owners(games, wanted):
    return {row[0]: item["id"] for item in games for row in item["results"] if row[0] in wanted}


def _examples(db, games, samples):
    wanted = {example["position_id"] for sample in samples for example in sample["examples"]}
    if not wanted:
        return True
    owners = _owners(games, wanted)
    placeholders = ",".join("?" for _ in wanted)
    rows = db.connection.execute(
        f"SELECT id,game_id FROM positions WHERE id IN ({placeholders})", tuple(wanted)
    ).fetchall()
    return len(rows) == len(wanted) and all(owners.get(row[0]) == row[1] for row in rows)


def frontier_matches(state, candidates, frontier, signatures):
    return (
        frontier == state["frontier"]
        and signatures == state["checked"]
        and matches_frontier(state, candidates)
    )


def current(db, state, candidates, samples, before):
    return (
        _dates(candidates, state["games"])
        and _examples(db, state["games"][:40], samples)
        and db.connection.execute("PRAGMA data_version").fetchone()[0] == before
    )
