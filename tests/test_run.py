"""
Unit test file.
"""

import unittest
from pathlib import Path

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.run import run

COMMAND = "fastled-wasm-compiler --help"

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"


COMPILER_FLAGS = TEST_DATA / "compiler_flags.py"
MAPPED_DIR = TEST_DATA / "mapped"
COMPILER_ROOT = TEST_DATA / "compiler_root"
FASTLED_COMPILER_DIR = TEST_DATA / "fastled_compiler_dir"

ASSETS_DIR = TEST_DATA / "assets"
INDEX_HTML = ASSETS_DIR / "index.html"
STYLE_CSS = ASSETS_DIR / "style.css"
INDEX_JS = ASSETS_DIR / "index.js"


ENABLED = False


class MainTester(unittest.TestCase):
    """Main tester class."""

    @unittest.skipUnless(ENABLED, "CLI test marked as disabled")
    def test_run(self) -> None:
        """Test command line interface (CLI)."""
        args: Args = Args(
            compiler_root=COMPILER_ROOT,
            assets_dirs=ASSETS_DIR,
            fastled_compiler_dir=FASTLED_COMPILER_DIR,
            mapped_dir=MAPPED_DIR,
            keep_files=False,
            only_copy=False,
            only_insert_header=False,
            only_compile=False,
            profile=False,
            disable_auto_clean=False,
            no_platformio=False,
            debug=False,
            quick=False,
            release=False,
        )
        rtn = run(args)
        self.assertEqual(0, rtn)


if __name__ == "__main__":
    unittest.main()
