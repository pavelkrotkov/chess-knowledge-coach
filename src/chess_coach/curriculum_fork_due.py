"""Read one bounded page of due owner-bound fork items."""


def fork_rows(db, now, extra, values, limit, order):
    query = """SELECT id,source_type,source_ref,due,julianday(due) AS due_order
        FROM training_items INDEXED BY idx_curriculum_fork_due
        WHERE source_type='unified_owned_fork' AND skill='fork' AND operation='execute'
        AND lower(due) != 'now' AND julianday(due) <= julianday(?)"""
    query += extra + f" ORDER BY {order} LIMIT ?"
    return db.connection.execute(query, [now.isoformat(), *values, limit]).fetchall()
