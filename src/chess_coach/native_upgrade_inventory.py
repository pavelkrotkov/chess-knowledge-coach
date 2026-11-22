"""Collect bounded aggregate index inputs for a native schema upgrade."""

MAX_ROWS = 50_000_000
CAPTURE = "source_type='unified_owned_capture' AND skill='hanging_piece'"
FORK = "source_type='unified_owned_fork' AND skill='fork'"
PUBLIC_MATE = "source_type='unified_public_m1' AND skill='mate_in_one'"
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


def _source_keys(connection):
    row = connection.execute(
        """SELECT count(*),coalesce(sum(typeof(id)!='integer' OR typeof(source_type)!='text'
        OR typeof(skill)!='text' OR typeof(operation)!='text' OR typeof(due)!='text'),0),
        coalesce(sum(lower(due)!='now'),0),coalesce(max(octet_length(source_type)),0),
        coalesce(max(octet_length(skill)),0),coalesce(max(octet_length(operation)),0),
        coalesce(max(octet_length(due)),0)
        FROM (SELECT id,source_type,skill,operation,due FROM training_items LIMIT ?)""",
        (MAX_ROWS + 1,),
    ).fetchone()
    if row[0] > MAX_ROWS or row[1]:
        raise ValueError("source index inventory incomplete or unsupported")
    return dict(
        zip(
            (
                "source_index_rows",
                "source_due_rows",
                "source_type_max_bytes",
                "skill_max_bytes",
                "operation_max_bytes",
                "due_max_bytes",
            ),
            (row[0], *row[2:]),
            strict=True,
        )
    )


def inventory(connection):
    result = _engine(connection)
    result.update(_source_keys(connection))
    for condition, name in (
        (MATE, "mate"),
        (CAPTURE, "capture"),
        (FORK, "fork"),
        (PUBLIC_MATE, "public_mate"),
    ):
        result.update(_training(connection, condition, name))
    return result
