"""Preserve each generated lesson as an append-only version."""


def add_lessons(connection):
    connection.execute(
        """CREATE TABLE IF NOT EXISTS lesson_versions (
            id INTEGER PRIMARY KEY,
            subject TEXT NOT NULL,
            lesson_json TEXT NOT NULL,
            generator_model TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            input_json TEXT NOT NULL,
            generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_lesson_versions_subject ON lesson_versions(subject, id)"
    )
