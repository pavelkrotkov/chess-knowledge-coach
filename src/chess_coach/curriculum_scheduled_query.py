"""Read one bounded page of existing puzzle and owner-bound schedules."""


def scheduled_rows(db, after, limit):
    index = "idx_curriculum_scheduled" if db.compat32 else "idx_curriculum_unified_scheduled"
    source = (
        "source_type='puzzle'" if db.compat32 else "source_type IN ('puzzle','unified_corpus_m1')"
    )
    return db.connection.execute(
        f"""SELECT id,source_type,source_ref,last_review FROM training_items INDEXED BY {index}
            WHERE id>? AND {source} AND skill='mate_in_one' AND operation='execute'
            ORDER BY id LIMIT ?""",
        (after, limit + 1),
    ).fetchall()
