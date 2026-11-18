import json
import os
import subprocess
import sys
from pathlib import Path

from scrapers.commit_gate import should_commit

ROOT = Path(__file__).resolve().parents[1]


def test_feed_timestamp_alone_is_not_a_commit() -> None:
    before = {"updated": "2026-11-17T21:46:38-05:00", "items": [{"id": "fr-1"}]}
    after = {"updated": "2026-11-17T23:40:03-05:00", "items": [{"id": "fr-1"}]}
    assert should_commit([("docs/data/federal.json", before, after)]) is False
    assert should_commit([("docs/data/trades.json", before, after)]) is False


def test_new_or_changed_record_is_a_commit() -> None:
    before = {"updated": "a", "items": [{"id": "fr-1", "title": "Old"}]}
    added = {"updated": "b", "items": [{"id": "fr-1", "title": "Old"}, {"id": "fr-2"}]}
    edited = {"updated": "b", "items": [{"id": "fr-1", "title": "New"}]}
    assert should_commit([("docs/data/federal.json", before, added)]) is True
    assert should_commit([("docs/data/trades.json", before, edited)]) is True


def test_status_rows_alone_are_not_a_commit() -> None:
    before = {
        "updated": "a",
        "items": [{"id": "federal-register", "lastRun": "a", "records": 19, "errors": []}],
    }
    after = {
        "updated": "b",
        "items": [
            {
                "id": "federal-register",
                "lastRun": "b",
                "records": 0,
                "errors": ["Federal Register response did not include results"],
            }
        ],
    }
    assert should_commit([("docs/data/status.json", before, after)]) is False


def test_cursor_window_alone_is_not_a_commit() -> None:
    before = {
        "window": ["2026-11-16", "2026-11-17"],
        "completed_through": "2026-11-17",
        "tasks": [],
    }
    after = {
        "window": ["2026-11-17", "2026-11-17"],
        "completed_through": "2026-11-17",
        "tasks": [],
    }
    assert should_commit([("state/federal-register.json", before, after)]) is False


def test_cursor_progress_is_a_commit() -> None:
    before = {
        "window": ["2026-11-16", "2026-11-16"],
        "completed_through": "2026-11-16",
        "tasks": [{"kind": "executive_orders", "start": "2026-11-16", "end": "2026-11-16"}],
    }
    cleared = {
        "window": ["2026-11-16", "2026-11-16"],
        "completed_through": "2026-11-16",
        "tasks": [],
    }
    advanced = {
        "window": ["2026-11-16", "2026-11-18"],
        "completed_through": "2026-11-18",
        "tasks": [],
    }
    assert should_commit([("state/federal-register.json", before, cleared)]) is True
    assert should_commit([("state/house-votes.json", before, advanced)]) is True


def test_quarantine_file_is_a_commit() -> None:
    path = "state/quarantine/federal-register/2026-1.json"
    assert should_commit([(path, None, {"reason": "missing title", "record": {}})]) is True


def test_timestamp_noise_with_a_real_record_still_commits() -> None:
    changes = [
        (
            "docs/data/federal.json",
            {"updated": "a", "items": []},
            {"updated": "b", "items": [{"id": "fr-1"}]},
        ),
        (
            "docs/data/status.json",
            {"updated": "a", "items": []},
            {"updated": "b", "items": [{"id": "federal-register", "lastRun": "b"}]},
        ),
        (
            "state/federal-register.json",
            {"window": ["2026-11-16", "2026-11-16"], "completed_through": "2026-11-16"},
            {"window": ["2026-11-16", "2026-11-18"], "completed_through": "2026-11-18"},
        ),
    ]
    assert should_commit(changes) is True


def test_cli_reads_the_index(tmp_path: Path) -> None:
    _git(tmp_path, ["init"])
    _git(tmp_path, ["config", "user.email", "test@example.com"])
    _git(tmp_path, ["config", "user.name", "test"])
    data = tmp_path / "docs" / "data"
    state = tmp_path / "state"
    data.mkdir(parents=True)
    state.mkdir()
    _write(data / "federal.json", {"updated": "a", "items": []})
    _write(data / "trades.json", {"updated": "a", "items": []})
    _write(data / "status.json", {"updated": "a", "items": []})
    _write(
        state / "federal-register.json",
        {"window": ["2026-11-16", "2026-11-16"], "completed_through": "2026-11-16", "tasks": []},
    )
    _git(tmp_path, ["add", "docs", "state"])
    _git(tmp_path, ["commit", "-m", "init"])

    _write(data / "federal.json", {"updated": "b", "items": []})
    _write(data / "status.json", {"updated": "b", "items": [{"id": "house-votes", "lastRun": "b"}]})
    _write(
        state / "federal-register.json",
        {"window": ["2026-11-17", "2026-11-18"], "completed_through": "2026-11-16", "tasks": []},
    )
    _git(tmp_path, ["add", "docs", "state"])
    assert _gate(tmp_path) == 1

    _write(data / "federal.json", {"updated": "b", "items": [{"id": "fr-2026-1"}]})
    _git(tmp_path, ["add", "docs/data/federal.json"])
    assert _gate(tmp_path) == 0


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _git(repo: Path, args: list[str]) -> None:
    subprocess.check_call(["git", *args], cwd=repo, stdout=subprocess.DEVNULL)


def _gate(repo: Path) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-m", "scrapers.commit_gate"],
        cwd=repo,
        env=env,
        check=False,
    )
    return completed.returncode
