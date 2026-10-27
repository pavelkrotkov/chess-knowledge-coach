from pathlib import Path

import pytest
from radon.metrics import mi_visit

from scripts import quality
from scripts.quality import measure, production_files


def test_detects_complex_nested_async_method_and_lambda() -> None:
    source = """class Example:
    async def outer(self):
        def inner(x):
            if x and x and x and x and x and x and x and x:
                return x
        return lambda x: x if x else 0
"""
    _, functions = measure(source)
    assert (3, "Example.outer.inner", 9) in functions
    assert (6, "Example.outer.<lambda>", 2) in functions


def test_low_maintainability_and_documented_radon_formula() -> None:
    source = "\n".join(f"x{i} = {i} + {i + 1}" for i in range(2000))
    mi, _ = measure(source)
    assert mi <= 50
    assert mi == mi_visit(source, multi=False)


def test_missing_sources_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        production_files(tmp_path)


@pytest.mark.parametrize(
    "source",
    [
        "def too_complex(x):\n    if x and x and x and x and x and x and x and x: return x\n",
        "\n".join(f"x{i} = {i} + {i + 1}" for i in range(2000)),
    ],
)
def test_check_fails_for_violations_but_report_only_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    package = tmp_path / "src/chess_coach"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "fixture.py").write_text(source)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "quality.py").write_text("")
    monkeypatch.setattr(quality, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["quality.py", "--check"])
    assert quality.main() == 1
    monkeypatch.setattr("sys.argv", ["quality.py", "--report-only"])
    assert quality.main() == 0
