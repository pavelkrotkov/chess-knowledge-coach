"""Regression tests for the JavaScript quality gate."""

import subprocess
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts/js-quality.cjs"
COMPLEX = """function bad(x) {
  if (x === 0) return 0;
  if (x === 1) return 1;
  if (x === 2) return 2;
  if (x === 3) return 3;
  if (x === 4) return 4;
  if (x === 5) return 5;
  if (x === 6) return 6;
  if (x === 7) return 7;
  return x;
}
"""


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(CHECKER)], cwd=root, capture_output=True, text=True, check=False
    )


def make_source(root: Path) -> Path:
    board = root / "src/chess_coach/static/board.js"
    board.parent.mkdir(parents=True)
    board.write_text("function good(x) { return x + 1; }\n")
    (root / "scripts").mkdir()
    return board


@pytest.mark.parametrize(
    "directive",
    ["", "/* eslint-disable complexity */\n", "/* eslint complexity: off */\n"],
)
def test_inline_configuration_cannot_disable_complexity(tmp_path: Path, directive: str) -> None:
    board = make_source(tmp_path)
    board.write_text(directive + COMPLEX)
    result = run_checker(tmp_path)
    assert result.returncode != 0
    assert "complexity of 9" in result.stderr


def test_valid_javascript_passes(tmp_path: Path) -> None:
    make_source(tmp_path)
    assert run_checker(tmp_path).returncode == 0


@pytest.mark.parametrize("kind", ["directory", "file", "src_root", "scripts_root", "dangling"])
def test_symlinks_fail_closed(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    if kind == "src_root":
        make_source(target)
        (root / "src").symlink_to(target / "src", target_is_directory=True)
        (root / "scripts").mkdir()
    elif kind == "scripts_root":
        make_source(root)
        (target / "bad.js").write_text(COMPLEX)
        (root / "scripts").rmdir()
        (root / "scripts").symlink_to(target, target_is_directory=True)
    else:
        board = make_source(root)
        (target / "bad.js").write_text(COMPLEX)
        if kind == "directory":
            (board.parent / "linked").symlink_to(target, target_is_directory=True)
        elif kind == "file":
            (board.parent / "linked.js").symlink_to(target / "bad.js")
        else:
            (board.parent / "missing.js").symlink_to(target / "missing.js")
    result = run_checker(root)
    assert result.returncode != 0
    assert "Symlink:" in result.stderr
