"""
Unit test file.
"""

import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.run_compile import run_compile as run

COMMAND = "fastled-wasm-compiler --help"

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"


COMPILER_FLAGS = TEST_DATA / "compiler_flags.py"
MAPPED_DIR = TEST_DATA / "mapped"
SKETCH_DIR = MAPPED_DIR / "sketch"

COMPILER_ROOT = TEST_DATA / "compiler_root"

ASSETS_DIR = TEST_DATA / "assets"

OUTPUT_ARTIFACT_DIR = TEST_DATA / "fastled_js"

_ENABLED = False


class MainTester(unittest.TestCase):
    """Main tester class."""

    def setUp(self) -> None:
        """Set up test environment."""
        fljs = OUTPUT_ARTIFACT_DIR
        if fljs.exists():
            shutil.rmtree(fljs, ignore_errors=True)

    @unittest.skipIf(not _ENABLED, "Skipping test as it is not enabled.")
    @patch("fastled_wasm_compiler.compile._pio_compile_cmd_list")
    def test_run_with_no_platformio(self, mock_pio_compile: MagicMock) -> None:
        """Test command line interface (CLI) with no_platformio=True."""

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
            no_platformio=True,
            debug=False,
            fast_debug=False,
            quick=False,
            release=False,
            clear_ccache=False,
            strict=False,
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

    @unittest.skipIf(not _ENABLED, "Skipping test as it is not enabled.")
    @patch("fastled_wasm_compiler.compile._new_compile_cmd_list")
    def test_run_with_platformio_deprecated(self, mock_new_compile: MagicMock) -> None:
        """Test command line interface (CLI) with no_platformio=False (now deprecated and falls back to non-PlatformIO)."""

        mock_new_compile.return_value = ["echo", "fake compile"]

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
            no_platformio=False,  # Test deprecation: this should fall back to non-PlatformIO
            debug=False,
            fast_debug=False,
            quick=False,
            release=False,
            clear_ccache=False,
            strict=False,
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
