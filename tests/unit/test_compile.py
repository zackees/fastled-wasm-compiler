"""
Unit test file.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler import compile
from fastled_wasm_compiler.types import BuildMode

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"
COMPILER_ROOT = TEST_DATA / "compiler_root"

_ENABLED = True


class MainTester(unittest.TestCase):
    """Main tester class."""

    @unittest.skipIf(not _ENABLED, "Skipping test as it is not enabled.")
    @patch("fastled_wasm_compiler.compile._pio_compile_cmd_list")
    def test_run(self, mock_pio_compile: MagicMock) -> None:
        """Test command line interface (CLI)."""
        mock_pio_compile.return_value = ["echo", "fake compile"]

        # Run the test
        compiler_root = COMPILER_ROOT
        build_mode = BuildMode.QUICK
        auto_clean = True
        no_platformio = False
        rtn = compile.compile(compiler_root, build_mode, auto_clean, no_platformio)

        # Verify results
        self.assertEqual(0, rtn)
        mock_pio_compile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
