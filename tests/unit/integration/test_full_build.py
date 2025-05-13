"""
Unit test file.
"""

import unittest
from pathlib import Path

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent.parent

DOCKER_FILE = PROJECT_ROOT / "Dockerfile"


class FullBuildTester(unittest.TestCase):
    """Main tester class."""

    def test_sanity(self) -> None:
        """Test command line interface (CLI)."""
        self.assertTrue(DOCKER_FILE.exists(), "Dockerfile does not exist")


if __name__ == "__main__":
    unittest.main()
