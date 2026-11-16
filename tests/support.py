from datetime import date
from pathlib import Path

from scrapers.context import RunContext


def make_context(tmp_path: Path, client, **overrides) -> RunContext:
    values = {
        "client": client,
        "federal_path": tmp_path / "federal.json",
        "trades_path": tmp_path / "trades.json",
        "status_path": tmp_path / "status.json",
        "state_dir": tmp_path / "state",
        "cli_start": date(2026, 11, 12),
        "cli_end": date(2026, 11, 12),
        "today": date(2026, 11, 16),
        "now": "2026-11-16T12:00:00-05:00",
    }
    values.update(overrides)
    return RunContext(**values)
