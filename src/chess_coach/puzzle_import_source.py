"""Check snapshot identity and controlled SQLite WAL configuration."""

from pathlib import Path

from .db import Database
from .puzzle_import_failure import fail
from .puzzle_import_input import snapshot_path, verify_snapshot


def signature(source: Path) -> tuple:
    info = source.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def unchanged(source: Path, expected: tuple) -> None:
    if signature(source) != expected:
        raise ValueError("decoded CSV changed during import")


def configure_wal(db: Database, enable: bool) -> None:
    if enable and db.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
        raise ValueError("SQLite WAL is not supported by this database")


def source_snapshot(
    db: Database, path: str | Path, project_root: str | Path, version: str, digest: str
) -> tuple[Path, tuple]:
    try:
        source = snapshot_path(path, project_root)
        expected = signature(source)
        verify_snapshot(source, digest)
        unchanged(source, expected)
        return source, expected
    except (OSError, ValueError):
        _fail_source(db, path, version, digest)
        raise ValueError("decoded CSV is unavailable or its checksum does not match") from None


def _fail_source(db: Database, path: str | Path, version: str, digest: str) -> None:
    row = db.connection.execute(
        """SELECT c.id,c.state,i.csv_path,i.csv_sha256 FROM puzzle_corpora c
        JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.version=?""",
        (version,),
    ).fetchone()
    if (
        row is not None
        and row["state"] == "staging"
        and row["csv_sha256"] == digest
        and str(Path(path).resolve()) == row["csv_path"]
    ):
        fail(db, row["id"], "decoded CSV is unavailable or changed")
