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

INDEX_HTML = TEST_DATA / "index.html"
STYLE_CSS = TEST_DATA / "style.css"
INDEX_JS = TEST_DATA / "index.js"
COMPILER_FLAGS = TEST_DATA / "compiler_flags.py"
MAPPED_DIR = TEST_DATA / "mapped"
COMPILER_ROOT = TEST_DATA / "compiler_root"
FASTLED_COMPILER_DIR = TEST_DATA / "fastled_compiler_dir"


ENABLED = False


class MainTester(unittest.TestCase):
    """Main tester class."""

    @unittest.skipUnless(ENABLED, "CLI test marked as disabled")
    def test_run(self) -> None:
        """Test command line interface (CLI)."""
        args: Args = Args(
            compiler_root=COMPILER_ROOT,
            index_html=INDEX_HTML,
            style_css=STYLE_CSS,
            index_js=INDEX_JS,
            compiler_flags=COMPILER_FLAGS,
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
