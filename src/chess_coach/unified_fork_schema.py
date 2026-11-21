"""Index the bounded owner-bound fork review pages."""


def add_fork_indexes(connection):
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_fork_due
        ON training_items(julianday(due),id) WHERE source_type='unified_owned_fork'
        AND skill='fork' AND operation='execute' AND lower(due) != 'now'""")
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_fork_scheduled
        ON training_items(id) WHERE source_type='unified_owned_fork'
        AND skill='fork' AND operation='execute'""")
