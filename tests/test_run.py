"""
Unit test file.
"""

import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.run import run

COMMAND = "fastled-wasm-compiler --help"

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"


COMPILER_FLAGS = TEST_DATA / "compiler_flags.py"
MAPPED_DIR = TEST_DATA / "mapped"
SKETCH_DIR = MAPPED_DIR / "sketch"

COMPILER_ROOT = TEST_DATA / "compiler_root"

ASSETS_DIR = TEST_DATA / "assets"

OUTPUT_ARTIFACT_DIR = TEST_DATA / "fastled_js"


class MainTester(unittest.TestCase):
    """Main tester class."""

    def setUp(self):
        """Set up test environment."""
        fljs = OUTPUT_ARTIFACT_DIR
        if fljs.exists():
            shutil.rmtree(fljs, ignore_errors=True)

    @patch("fastled_wasm_compiler.compile._pio_compile_cmd_list")
    def test_run(self, mock_pio_compile: MagicMock) -> None:
        """Test command line interface (CLI)."""

        mock_pio_compile.return_value = ["echo", "fake compile"]

        args: Args = Args(
            compiler_root=COMPILER_ROOT,
            assets_dirs=ASSETS_DIR,
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

        # verify that the expected output artifacts exist
        output_artifact_dir = SKETCH_DIR / "fastled_js"
        self.assertTrue(
            output_artifact_dir.exists(), "Output artifact directory does not exist"
        )
        # known artifacts are
        output_files = [
            "files.json",
            "index.html",
            "index.css",
            "index.js",
            # "fastled.wasm",  # not present in mock env
            "modules/module1.js",
            "modules/module2.js",
        ]

        for file in output_files:
            file_path = output_artifact_dir / file
            self.assertTrue(
                file_path.exists(), f"Output artifact {file} does not exist"
            )


if __name__ == "__main__":
    unittest.main()
