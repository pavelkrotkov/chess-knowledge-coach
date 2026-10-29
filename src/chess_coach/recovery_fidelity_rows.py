"""Compare typed rows, including hidden rowids, in bounded cursor order."""

import struct
from itertools import zip_longest

from .recovery_fidelity_query import query_for

_MISSING = object()


def _equal(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right, strict=True):
        if type(a) is not type(b):
            return False
        if isinstance(a, float):
            if struct.pack(">d", a) != struct.pack(">d", b):
                return False
        elif a != b:
            return False
    return True


def compare_rows(reader, writer, name, without_rowid, deadline):
    query = query_for(reader, name, without_rowid)
    for connection in (reader, writer):
        plan = connection.execute("EXPLAIN QUERY PLAN " + query)
        if any(b"USE TEMP B-TREE" in row[3] for row in plan):
            raise ValueError("unsupported database schema")
    first = reader.execute(query)
    second = writer.execute(query)
    for left, right in zip_longest(first, second, fillvalue=_MISSING):
        deadline.check()
        if left is _MISSING or right is _MISSING or not _equal(left, right):
            raise ValueError("database logical fidelity verification failed")
