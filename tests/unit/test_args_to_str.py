"""
Unit test file.
"""

import shutil
import unittest
from pathlib import Path

from fastled_wasm_compiler.args import Args

COMMAND = "fastled-wasm-compiler --help"

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"


COMPILER_FLAGS = TEST_DATA / "compiler_flags.py"
MAPPED_DIR = TEST_DATA / "mapped"
SKETCH_DIR = MAPPED_DIR / "sketch"

COMPILER_ROOT = TEST_DATA / "compiler_root"

ASSETS_DIR = TEST_DATA / "assets"

OUTPUT_ARTIFACT_DIR = TEST_DATA / "fastled_js"


class ArgConverstionTester(unittest.TestCase):
    """Main tester class."""

    def setUp(self):
        """Set up test environment."""
        fljs = OUTPUT_ARTIFACT_DIR
        if fljs.exists():
            shutil.rmtree(fljs, ignore_errors=True)

    def test_arg_conversion_and_back(self) -> None:
        """Test command line interface (CLI)."""

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
            quick=True,
            release=False,
            clear_ccache=False,
            strict=False,
        )

        cmd_args = args.to_cmd_args()
        args2 = Args.parse_args(cmd_args)

        print(f"args: {args}")
        print(f"args2: {args2}")

        self.assertEqual(args, args2)


if __name__ == "__main__":
    unittest.main()
