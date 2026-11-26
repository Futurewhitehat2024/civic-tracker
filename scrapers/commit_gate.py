"""Decide whether a scrape run has anything worth committing.

Every run rewrites feed `updated` timestamps, status rows, and the cursor
`window`. Those diffs are not published records. A commit still happens when
federal or trade items change, or when other cursor state has to be saved so
the next run can resume.
"""

import json
import subprocess
from pathlib import Path

FEED_PATHS = frozenset(
    {
        "docs/data/federal.json",
        "docs/data/federal-notices.json",
        "docs/data/trades.json",
        "docs/data/deadlines.json",
        "docs/data/counties.json",
    }
)
STATUS_PATH = "docs/data/status.json"
# Derived files are committed with record changes, not for a timestamp-only rewrite.
DERIVED_PATHS = frozenset(
    {
        "docs/data/coverage.json",
        "docs/data/manifest.json",
        "docs/data/deadlines.ics",
        "docs/data/v1/manifest.json",
        "docs/data/v1/coverage.json",
        "docs/data/v1/federal.json",
        "docs/data/v1/federal-notices.json",
        "docs/data/v1/deadlines.json",
        "docs/data/v1/counties.json",
        "docs/data/v1/federal.csv",
        "docs/data/v1/federal-notices.csv",
        "docs/data/v1/deadlines.csv",
        "docs/data/v1/counties.csv",
        "docs/data/v1/coverage.csv",
    }
)


def should_commit(changes: list[tuple[str, object, object]]) -> bool:
    for path, before, after in changes:
        normalized = path.replace("\\", "/")
        if normalized in FEED_PATHS:
            if _records(before) != _records(after):
                return True
            continue
        if normalized == STATUS_PATH:
            continue
        if normalized in DERIVED_PATHS or normalized.startswith("docs/data/v1/"):
            continue
        if normalized.startswith("state/"):
            if _state_core(before) != _state_core(after):
                return True
            continue
        if before != after:
            return True
    return False


def staged_changes(repo: Path | None = None) -> list[tuple[str, object, object]]:
    root = repo or Path.cwd()
    raw = _git(root, ["diff", "--cached", "--name-only", "-z"])
    paths = [part for part in raw.decode().split("\0") if part]
    return [(path, _show(root, f"HEAD:{path}"), _show(root, f":{path}")) for path in paths]


def main() -> int:
    if should_commit(staged_changes()):
        return 0
    return 1


def _records(payload: object) -> object:
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    return payload


def _state_core(payload: object) -> object:
    """Cursor progress, without the derived date window."""
    if not isinstance(payload, dict):
        return payload
    return {key: value for key, value in payload.items() if key != "window"}


def _show(repo: Path, spec: str) -> object:
    try:
        raw = _git(repo, ["show", spec])
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 128:
            return None
        raise
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode("utf-8", "replace")


def _git(repo: Path, args: list[str]) -> bytes:
    return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    raise SystemExit(main())
