"""
Unit test file.
"""

import unittest
from pathlib import Path

from fastled_wasm_compiler.compile import compile
from fastled_wasm_compiler.types import BuildMode

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"

# INDEX_HTML = TEST_DATA / "index.html"
# STYLE_CSS = TEST_DATA / "style.css"
# INDEX_JS = TEST_DATA / "index.js"
# COMPILER_FLAGS = TEST_DATA / "compiler_flags.py"
# MAPPED_DIR = TEST_DATA / "mapped"
COMPILER_ROOT = TEST_DATA / "compiler_root"
# FASTLED_COMPILER_DIR = TEST_DATA / "fastled_compiler_dir"


ENABLED = False


class MainTester(unittest.TestCase):
    """Main tester class."""

    @unittest.skipUnless(ENABLED, "CLI test marked as disabled")
    def test_run(self) -> None:
        """Test command line interface (CLI)."""
        compiler_root = COMPILER_ROOT
        build_mode = BuildMode.QUICK
        auto_clean = True
        no_platformio = False
        rtn = compile(compiler_root, build_mode, auto_clean, no_platformio)
        self.assertEqual(0, rtn)


if __name__ == "__main__":
    unittest.main()
