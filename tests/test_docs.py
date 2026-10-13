"""The README examples run and print what they say; metadata agrees with the code."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import periodictimer

ROOT = Path(__file__).resolve().parents[1]

OUTPUTS = [
    ["tick 1", "tick 2", "tick 3", "3"],
    [
        "skip [1.0, 5.0, 6.0, 7.0] 3",
        "coalesce [1.0, 4.5, 5.0, 6.0] 2",
        "burst [1.0, 4.5, 4.5, 4.5] 0",
    ],
    ["<PeriodicTimer refresh_cache every 60.0s, idle>"],
    ["attempt 1: database is down", "attempt 2: database is down"],
    ["beat 1", "beat 2"],
]


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _blocks() -> list[str]:
    return re.findall(r"```python\n(.*?)```", _readme(), flags=re.DOTALL)


def test_there_is_one_expected_output_per_example() -> None:
    assert len(_blocks()) == len(OUTPUTS)


@pytest.mark.parametrize("index", range(len(OUTPUTS)))
def test_each_example_prints_its_output(index: int, capsys: pytest.CaptureFixture[str]) -> None:
    exec(compile(_blocks()[index], "README.md", "exec"), {"__name__": "readme"})

    assert capsys.readouterr().out.splitlines() == OUTPUTS[index]


@pytest.mark.parametrize("index", range(len(OUTPUTS)))
def test_each_printed_line_is_shown_as_a_comment(index: int) -> None:
    comments = re.findall(r"^# (.+)$", _blocks()[index], flags=re.MULTILINE)

    assert comments == OUTPUTS[index]


def test_every_public_name_appears_in_the_readme() -> None:
    for name in periodictimer.__all__:
        assert f"`{name}`" in _readme(), name


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == periodictimer.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{periodictimer.__version__}]" in text


def test_no_em_dash_in_any_shipped_text() -> None:
    files = [*ROOT.glob("*.md"), *ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py")]
    for path in files:
        assert chr(0x2014) not in path.read_text(encoding="utf-8"), path


def test_no_source_file_is_longer_than_two_hundred_lines() -> None:
    for path in [*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py")]:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 200, path
