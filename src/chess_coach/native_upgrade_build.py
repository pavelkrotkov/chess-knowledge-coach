"""Recognize the SQLite build used by the conditional capacity proof."""

import sqlite3
import struct

SOURCE_ID = "c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9"
OPTIONS = {"ENABLE_DBSTAT_VTAB", "SYSTEM_MALLOC", "TEMP_STORE=1"}


def supported(connection):
    source = connection.execute("SELECT sqlite_source_id()").fetchone()[0].split()
    options = {row[0] for row in connection.execute("PRAGMA compile_options")}
    return (
        sqlite3.sqlite_version == "3.53.1"
        and len(source) == 3
        and source[-1] == SOURCE_ID
        and options >= OPTIONS
        and "DEFAULT_MEMSTATUS=0" not in options
        and struct.calcsize("P") == 8
    )
