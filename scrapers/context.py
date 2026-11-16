"""Shared inputs for one scraper run."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


@dataclass
class RunContext:
    client: Any
    federal_path: Path
    trades_path: Path
    status_path: Path
    state_dir: Path
    cli_start: date | None
    cli_end: date | None
    today: date
    now: str


@dataclass
class Outcome:
    records: int = 0
    errors: list[str] | None = None
    checked: bool = False

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
