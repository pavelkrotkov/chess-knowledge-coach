"""Find analysis-linked tables through declared foreign keys and evidence."""

from .recovery_fidelity_tables import tables


def dependent_tables(connection):
    known = tables(connection)
    dependencies = {}
    for name, without_rowid in known:
        refs = connection.execute(
            'SELECT "table" FROM pragma_foreign_key_list(?)', (name.decode(),)
        ).fetchall()
        dependencies[name] = (without_rowid, {row[0] for row in refs})
    selected = _closure(dependencies)
    return [(name, dependencies[name][0]) for name in sorted(selected - {b"analysis_runs"})]


def _closure(dependencies):
    # Evidence and detector records also refer to runs through immutable JSON.
    selected = {
        b"analysis_runs",
        b"evidence_mappings",
        b"mapping_runs",
        b"detector_facts",
        b"detector_runs",
    } & dependencies.keys()
    while True:
        expanded = selected | {name for name, (_, refs) in dependencies.items() if refs & selected}
        if expanded == selected:
            return selected
        selected = expanded
