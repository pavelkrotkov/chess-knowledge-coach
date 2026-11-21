"""Index the bounded owner-bound capture review pages."""


def add_capture_indexes(connection):
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_capture_due
        ON training_items(julianday(due),id) WHERE source_type='unified_owned_capture'
        AND skill='hanging_piece' AND operation='execute' AND lower(due) != 'now'""")
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_capture_scheduled
        ON training_items(id) WHERE source_type='unified_owned_capture'
        AND skill='hanging_piece' AND operation='execute'""")
