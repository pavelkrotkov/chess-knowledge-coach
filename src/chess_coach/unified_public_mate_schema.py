"""Index bounded, exact-source review pages."""


def add_public_mate_indexes(connection):
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_source_due
        ON training_items(source_type,skill,operation,julianday(due),id)
        WHERE lower(due) != 'now'""")
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_source_scheduled
        ON training_items(source_type,skill,operation,id)""")
