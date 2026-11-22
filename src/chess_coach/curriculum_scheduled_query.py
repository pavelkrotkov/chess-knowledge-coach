"""Read one bounded page of existing puzzle and owner-bound schedules."""


def scheduled_rows(db, after, limit):
    index = "idx_curriculum_scheduled" if db.compat32 else "idx_curriculum_unified_scheduled"
    source = (
        "source_type='puzzle'" if db.compat32 else "source_type IN ('puzzle','unified_corpus_m1')"
    )
    rows = list(
        db.connection.execute(
            f"""SELECT id,source_type,source_ref,last_review FROM training_items INDEXED BY {index}
            WHERE id>? AND {source} AND skill='mate_in_one' AND operation='execute'
            ORDER BY id LIMIT ?""",
            (after, limit + 1),
        ).fetchall()
    )
    if db.compat32:
        return rows
    rows.extend(
        db.connection.execute(
            """SELECT id,source_type,source_ref,last_review FROM training_items
        INDEXED BY idx_curriculum_capture_scheduled WHERE id>?
        AND source_type='unified_owned_capture' AND skill='hanging_piece'
        AND operation='execute' ORDER BY id LIMIT ?""",
            (after, limit + 1),
        ).fetchall()
    )
    rows.extend(
        db.connection.execute(
            """SELECT id,source_type,source_ref,last_review FROM training_items
        INDEXED BY idx_curriculum_fork_scheduled WHERE id>?
        AND source_type='unified_owned_fork' AND skill='fork'
        AND operation='execute' ORDER BY id LIMIT ?""",
            (after, limit + 1),
        ).fetchall()
    )
    rows.extend(
        db.connection.execute(
            """SELECT id,source_type,source_ref,last_review FROM training_items
        INDEXED BY idx_curriculum_source_scheduled WHERE id>?
        AND source_type='unified_public_m1' AND skill='mate_in_one'
        AND operation='execute' ORDER BY id LIMIT ?""",
            (after, limit + 1),
        ).fetchall()
    )
    rows.extend(
        db.connection.execute(
            """SELECT id,source_type,source_ref,last_review FROM training_items
        INDEXED BY idx_curriculum_source_scheduled WHERE id>?
        AND source_type='unified_canonical_promotion' AND skill='promotion'
        AND operation='execute' ORDER BY id LIMIT ?""",
            (after, limit + 1),
        ).fetchall()
    )
    return sorted(rows, key=lambda row: row["id"])[: limit + 1]
