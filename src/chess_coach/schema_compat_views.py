"""Install connection-local legacy projections and reject unsupported rows."""


def _text(value):
    if not isinstance(value, str) or not value:
        raise ValueError("invalid legacy detector or mapping value")
    return value


def _analysis(config, nnue, compatibility):
    if not all(isinstance(value, str) for value in (config, nnue, compatibility)):
        raise ValueError("invalid legacy analysis value")
    if not (config or nnue or compatibility):
        raise ValueError("compact analysis value unavailable")
    return config


def install(connection):
    """Install attested aliases before a connection enters query-only mode."""
    connection.execute("PRAGMA temp_store=MEMORY")
    if connection.execute("SELECT sqlite_compileoption_used('TEMP_STORE=0')").fetchone()[0]:
        raise ValueError("private temporary storage unavailable")
    if connection.execute("PRAGMA temp_store").fetchone()[0] != 2:
        raise ValueError("private temporary storage unavailable")
    connection.create_function("legacy_text", 1, _text)
    connection.create_function("legacy_analysis", 3, _analysis)
    connection.execute("""CREATE TEMP VIEW analysis_runs_read AS
        SELECT id,game_id,engine,engine_version,
        legacy_analysis(config_json,nnue,compatibility_json) AS config_json,
        binary_path,binary_version,nnue,compatibility_json,created_at FROM main.analysis_runs""")
    connection.execute("""CREATE TEMP VIEW detector_runs_read AS
        SELECT id,producer,position_id,detector_version,legacy_text(input_json) AS input_json,
        legacy_text(input_hash) AS input_hash,legacy_text(output_hash) AS output_hash,
        produced_at,status,supersedes_run_id FROM main.detector_runs""")
    connection.execute("""CREATE TEMP VIEW mapping_runs_read AS
        SELECT id,producer,position_id,subject,operation,scope_key,mapper_version,
        legacy_text(input_json) AS input_json,legacy_text(input_hash) AS input_hash,
        legacy_text(output_hash) AS output_hash,created_at,status,supersedes_run_id FROM main.mapping_runs""")
