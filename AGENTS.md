# Development Guide

This project uses `uv` for dependency management and execution. Do not create or activate a virtual environment manually.

## Setup

```bash
uv sync --dev
```

## Verification

```bash
uv run pytest
uv run pytest --cov
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pip-audit
uv run pre-commit run --all-files
```

Use focused commands while iterating, for example:

```bash
uv run pytest tests/test_ingest.py -q
uv run chess-coach --db /tmp/coach.sqlite ingest-pgn examples/example.pgn
```

Keep raw game data immutable, preserve provenance for analysis/inference, and do not infer mastery directly from centipawn loss. Use parameterized SQLite queries and explicit timeouts for network calls.
