"""
Unit test file.
"""

import unittest
import warnings
from pathlib import Path
from typing import Tuple

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
DOCKER_FILE = PROJECT_ROOT / "Dockerfile"
PYPROJECT_TOML = PROJECT_ROOT / "pyproject.toml"


def _find_version_in_docker() -> str:
    with open(DOCKER_FILE, "r") as f:
        for line in f:
            if line.startswith("ENV COMPILER_VERSION="):
                return line.split("=", 1)[1].strip()
    raise ValueError("Version not found in Dockerfile")


def _find_version_in_pyproject() -> str:
    with open(PYPROJECT_TOML, "r") as f:
        for line in f:
            if line.strip().startswith("version ="):
                return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("Version not found in pyproject.toml")


def _parse_semver(version: str) -> Tuple[int, int, int]:
    """
    Parse a SemVer string into its (major, minor, patch) components.
    Non-numeric or missing parts default to 0; prerelease/build metadata is ignored.
    """
    core = version.split("-", 1)[0].split("+", 1)[0]
    parts = core.split(".")
    nums = []
    for i in range(3):
        try:
            nums.append(int(parts[i]))
        except (IndexError, ValueError):
            nums.append(0)
    return tuple(nums)


class VersionMatchTester(unittest.TestCase):
    """Main tester class."""

    def test_semver_difference(self) -> None:
        docker_ver = _find_version_in_docker()
        pyproject_ver = _find_version_in_pyproject()
        dv = _parse_semver(docker_ver)
        pv = _parse_semver(pyproject_ver)

        # Compute absolute differences per segment
        diffs = [abs(a - b) for a, b in zip(dv, pv)]
        max_diff = max(diffs)

        if max_diff == 0:
            # Exact match → OK
            return
        if max_diff <= 2:
            # Patch/minor/major differ by 1–2 → warn but do not fail
            warnings.warn(
                f"Version difference of up to 2 detected "
                f"(Dockerfile={docker_ver}, pyproject.toml={pyproject_ver})"
            )
            return

        # Any segment differs by 3 or more → fail the test
        self.fail(
            f"Version difference of 3 or more detected "
            f"(Dockerfile={docker_ver}, pyproject.toml={pyproject_ver})"
        )


if __name__ == "__main__":
    unittest.main()
