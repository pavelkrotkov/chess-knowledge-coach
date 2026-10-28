"""Optional Maia adapter implementations and checkpoint configuration."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Protocol

from .maia_probabilities import _parse_probabilities


class MaiaAdapter(Protocol):
    model: str
    checkpoint: str
    adapter_version: str

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]: ...


@dataclass(frozen=True)
class UnavailableMaiaAdapter:
    model: str = "unavailable"
    checkpoint: str = "none"
    adapter_version: str = "offline-0.1.0"

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]:
        raise RuntimeError("Maia is unavailable; install and configure the optional adapter")


@dataclass(frozen=True)
class SubprocessMaiaAdapter:
    executable: str
    model: str
    checkpoint: str
    adapter_version: str = "subprocess-0.1.0"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.checkpoint or self.checkpoint in {"configured", "none"}:
            raise ValueError("Maia checkpoint must be an explicit reproducible identifier")

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]:
        try:
            completed = subprocess.run(
                [self.executable],
                input=json.dumps({"fen": fen, "moves": moves, "elo": elo}),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Maia adapter failed: {exc}") from exc
        return _parse_probabilities(completed.stdout)
