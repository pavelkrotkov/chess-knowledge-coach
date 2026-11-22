"""Read a bounded page of owner-bound canonical promotion reviews."""


def promotion_rows(db, now, extra, values, limit, order, *, forced=False):
    query = """SELECT id,source_type,source_ref,due,julianday(due) AS due_order
        FROM training_items INDEXED BY idx_curriculum_source_due
        WHERE source_type=? AND skill='promotion' AND operation='execute'
        AND lower(due) != 'now' AND julianday(due) <= julianday(?)"""
    query += extra + f" ORDER BY {order} LIMIT ?"
    source = "unified_canonical_forced_promotion" if forced else "unified_canonical_promotion"
    return db.connection.execute(query, [source, now.isoformat(), *values, limit]).fetchall()
