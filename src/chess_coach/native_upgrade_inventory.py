"""Collect bounded aggregate index inputs for a native schema upgrade."""

MAX_ROWS = 50_000_000
CAPTURE = "source_type='unified_owned_capture' AND skill='hanging_piece'"
FORK = "source_type='unified_owned_fork' AND skill='fork'"
MATE = "source_type IN ('puzzle','unified_corpus_m1') AND skill='mate_in_one'"


def _count(connection, query, label):
    count, invalid = connection.execute(query, (MAX_ROWS + 1,)).fetchone()
    if count > MAX_ROWS or invalid:
        raise ValueError("index key inventory incomplete or unsupported")
    return {label: count}


def _engine(connection):
    return _count(
        connection,
        """SELECT count(*),coalesce(sum(typeof(position_id)!='integer'),0)
        FROM (SELECT position_id FROM engine_outputs LIMIT ?)""",
        "engine_rows",
    )


def _training(connection, condition, name):
    query = f"""SELECT count(*),coalesce(sum(typeof(id)!='integer' OR typeof(due)!='text'),0)
        FROM (SELECT id,due FROM training_items
        WHERE {condition} AND operation='execute' LIMIT ?)"""
    return _count(connection, query, name + "_rows")


def inventory(connection):
    result = _engine(connection)
    for condition, name in ((MATE, "mate"), (CAPTURE, "capture"), (FORK, "fork")):
        result.update(_training(connection, condition, name))
    return result
