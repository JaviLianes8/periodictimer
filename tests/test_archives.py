"""Inspect built distributions and rebuild the wheel from the source archive."""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.environ.get("PERIODICTIMER_E2E") != "1", reason="set PERIODICTIMER_E2E=1 for archives"
)


def test_sdist_and_wheel_have_only_release_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(tmp_path), str(ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    wheel = tmp_path / "periodictimer-1.0.0-py3-none-any.whl"
    sdist = tmp_path / "periodictimer-1.0.0.tar.gz"
    package_files = {
        f"periodictimer/{path.name}"
        for path in (ROOT / "src/periodictimer").iterdir()
        if path.is_file() and path.suffix in (".py", ".typed")
    }
    dist_info = "periodictimer-1.0.0.dist-info/"
    with zipfile.ZipFile(wheel) as archive:
        expected = package_files | {
            dist_info + name for name in ("METADATA", "WHEEL", "RECORD", "licenses/LICENSE")
        }
        assert set(archive.namelist()) == expected
        metadata = BytesParser().parsebytes(archive.read(dist_info + "METADATA"))
        assert metadata["Version"] == "1.0.0"
        assert metadata["Requires-Python"] == ">=3.10"
        assert metadata["License-Expression"] == "MIT"
        assert "Development Status :: 5 - Production/Stable" in metadata.get_all("Classifier", [])
        assert all("extra == 'dev'" in dep for dep in metadata.get_all("Requires-Dist", []))
        for name in package_files:
            assert archive.read(name) == (ROOT / "src" / name).read_bytes()
        assert archive.read(dist_info + "licenses/LICENSE") == (ROOT / "LICENSE").read_bytes()
    with tarfile.open(sdist) as archive:
        names = {item.name for item in archive.getmembers() if item.isfile()}
        prefix = "periodictimer-1.0.0/"
        expected = {prefix + "src/" + name for name in package_files}
        expected |= {
            prefix + name
            for name in (
                "README.md",
                "GUIDE.md",
                "CHANGELOG.md",
                "LICENSE",
                "pyproject.toml",
                "PKG-INFO",
                ".gitignore",
            )
        }
        assert names == expected
    checked = subprocess.run(
        [sys.executable, "-m", "twine", "check", "--strict", str(wheel), str(sdist)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
