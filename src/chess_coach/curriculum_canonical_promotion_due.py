"""Read a bounded page of owner-bound canonical promotion reviews."""


def promotion_rows(db, now, extra, values, limit, order):
    query = """SELECT id,source_type,source_ref,due,julianday(due) AS due_order
        FROM training_items INDEXED BY idx_curriculum_source_due
        WHERE source_type='unified_canonical_promotion' AND skill='promotion' AND operation='execute'
        AND lower(due) != 'now' AND julianday(due) <= julianday(?)"""
    query += extra + f" ORDER BY {order} LIMIT ?"
    return db.connection.execute(query, [now.isoformat(), *values, limit]).fetchall()
