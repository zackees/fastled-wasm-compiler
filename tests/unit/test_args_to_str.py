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

    def test_arg_conversion_and_back_with_no_platformio(self) -> None:
        """Test command line interface (CLI) args conversion with no_platformio=True."""

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

    def test_arg_conversion_and_back_with_platformio(self) -> None:
        """Test command line interface (CLI) args conversion with no_platformio=False (deprecated, falls back to non-PlatformIO)."""

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
            no_platformio=False,  # Explicitly test with PlatformIO enabled
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

        # Since PlatformIO is deprecated, no_platformio will always default to True during parsing
        # even if the original Args object had no_platformio=False
        expected_args = Args(
            compiler_root=args.compiler_root,
            assets_dirs=args.assets_dirs,
            mapped_dir=args.mapped_dir,
            keep_files=args.keep_files,
            only_copy=args.only_copy,
            only_insert_header=args.only_insert_header,
            only_compile=args.only_compile,
            profile=args.profile,
            disable_auto_clean=args.disable_auto_clean,
            no_platformio=True,  # This gets overridden to True due to deprecation
            debug=args.debug,
            quick=args.quick,
            release=args.release,
            clear_ccache=args.clear_ccache,
            strict=args.strict,
        )
        self.assertEqual(expected_args, args2)

    def test_default_platformio_behavior(self) -> None:
        """Test that no_platformio defaults to False (though PlatformIO is now deprecated and falls back to non-PlatformIO)."""

        # Test with minimal required args - should default to no_platformio=False (but will show deprecation warning)
        cmd_args = [
            "--compiler-root",
            str(COMPILER_ROOT),
            "--assets-dirs",
            str(ASSETS_DIR),
            "--mapped-dir",
            str(MAPPED_DIR),
        ]

        args = Args.parse_args(cmd_args)

        # Verify the default argument parsing behavior (now defaults to non-PlatformIO since it's deprecated)
        self.assertTrue(
            args.no_platformio,
            "no_platformio should default to True since PlatformIO is deprecated",
        )


if __name__ == "__main__":
    unittest.main()
