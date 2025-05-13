"""
Unit test file.
"""

import unittest
from pathlib import Path

HERE = Path(__file__).parent

PROJECT_ROOT = HERE.parent.parent
DOCKER_FILE = PROJECT_ROOT / "Dockerfile"
PYPROJECT_TOML = PROJECT_ROOT / "pyproject.toml"


def _find_version_in_docker() -> str:
    # ENV COMPILER_VERSION=0.0.8
    with open(DOCKER_FILE, "r") as file:
        for line in file:
            if "ENV COMPILER_VERSION=" in line:
                return line.split("=")[1].strip()
    raise ValueError("Version not found in Dockerfile")


def _find_version_in_pyproject() -> str:
    # version = "0.0.8"
    with open(PYPROJECT_TOML, "r") as file:
        for line in file:
            if "version = " in line:
                return line.split("=")[1].strip().replace('"', "")
    raise ValueError("Version not found in pyproject.toml")


class VersionMatchTester(unittest.TestCase):
    """Main tester class."""

    def test_versions_match(self) -> None:
        """Test command line interface (CLI)."""
        docker_version = _find_version_in_docker()
        pyproject_version = _find_version_in_pyproject()

        self.assertEqual(
            docker_version,
            pyproject_version,
            f"Versions do not match: {docker_version} != {pyproject_version}",
        )


if __name__ == "__main__":
    unittest.main()
