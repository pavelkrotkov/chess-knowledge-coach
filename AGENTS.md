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
uv run python -m scripts.quality --check
uv run pip-audit
uv run pre-commit run --all-files
```

Use focused commands while iterating, for example:

```bash
uv run pytest tests/test_ingest.py -q
uv run chess-coach --db .venv/coach-example.sqlite ingest-pgn examples/example.pgn
```

Keep raw game data immutable, preserve provenance for analysis/inference, and do not infer mastery directly from centipawn loss. Use parameterized SQLite queries and explicit timeouts for network calls.

## Agent skills and execution

The issue tracker is GitHub Issues for `pavelkrotkov/chess-knowledge-coach`.
The approved triage labels are `ready-for-agent` and `ready-for-human`.
Use `README.md`, `kg.md`, and `docs/adr/ADR.md` for the existing domain and decisions.

Work in small, reviewable slices on gh-stack layers. The final commit requires
independent review and passing CI. Production Python must meet CC <= 8 per callable
and MI > 50 per module; see the metric policy in `README.md`. CI and pre-commit
enforce these thresholds. Issue #29 remains open for final verification after the
remaining release work.

## Proportional testing

Keep at most 200 collected pytest cases, including parametrized cases. Prefer a
small set of meaningful workflow, integrity, and privacy regressions over helper
mirrors and redundant edge-case matrices. CI reports coverage for visibility;
it is not a target or a substitute for useful tests.
