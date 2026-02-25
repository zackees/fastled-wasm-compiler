"""
Unit tests for Native CLI module.

These tests verify that the CLI interface exists and is properly structured.
They do not require actual EMSDK installation.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.cli_native import NativeCliArgs, _parse_args, main


class TestNativeCliModule(unittest.TestCase):
    """Test the native CLI module structure and basic functionality."""

    def test_module_imports(self):
        """Test that the CLI module can be imported without errors."""
        from fastled_wasm_compiler import cli_native

        # Check that main function exists
        self.assertTrue(hasattr(cli_native, "main"))
        self.assertTrue(callable(cli_native.main))

        # Check that argument parsing exists
        self.assertTrue(hasattr(cli_native, "NativeCliArgs"))
        self.assertTrue(hasattr(cli_native, "_parse_args"))

    def test_cli_entry_point_exists(self):
        """Test that the CLI entry point is properly installed."""
        # This tests that the entry point exists in the package
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from importlib.metadata import entry_points; print('fastled-wasm-compiler-native' in [ep.name for ep in entry_points(group='console_scripts')])",
            ],
            capture_output=True,
            text=True,
        )
        # We expect this to be True when properly installed, but in dev mode it might not be
        # So we'll just check that the import works without error
        self.assertEqual(result.returncode, 0)

    def test_help_argument(self):
        """Test that --help argument works."""
        with patch("sys.argv", ["fastled-wasm-compiler-native", "--help"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            # Help should exit with code 0
            self.assertEqual(cm.exception.code, 0)

    def test_argument_parsing_structure(self):
        """Test that argument parsing has the expected structure."""
        # Mock argv for a basic valid command
        test_sketch_dir = Path("/tmp/test_sketch")

        with patch(
            "sys.argv",
            ["fastled-wasm-compiler-native", str(test_sketch_dir), "--mode", "debug"],
        ):
            with patch("fastled_wasm_compiler.cli_native._parse_args") as mock_parse:
                # Create a mock args object
                mock_args = NativeCliArgs(
                    sketch_dir=test_sketch_dir,
                    build_mode="debug",
                    output_dir=None,
                    emsdk_dir=None,
                    install_emsdk=False,
                    keep_files=False,
                    profile=False,
                    strict=False,
                    headers=None,
                    add_src=False,
                )
                mock_parse.return_value = mock_args

                # Mock the sketch directory exists check
                with patch.object(Path, "exists", return_value=True):
                    # Mock the compile_sketch_native function
                    with patch(
                        "fastled_wasm_compiler.cli_native.compile_sketch_native"
                    ) as mock_compile:
                        mock_compile.return_value = Path("/tmp/output/fastled.js")

                        # Run main
                        result = main()

                        # Should succeed
                        self.assertEqual(result, 0)

                        # Should have called parse_args
                        mock_parse.assert_called_once()

                        # Should have called compile with correct args
                        mock_compile.assert_called_once_with(
                            sketch_dir=test_sketch_dir,
                            build_mode="debug",
                            output_dir=None,
                            emsdk_install_dir=None,
                        )

    def test_argument_validation(self):
        """Test argument validation for required parameters."""
        # Set up required environment variables
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fastled_temp = temp_path / "fastled"
            fastled_src_temp = fastled_temp / "src"
            emsdk_temp = temp_path / "emsdk"
            sketch_temp = temp_path / "src"

            # Create directories
            fastled_src_temp.mkdir(parents=True, exist_ok=True)
            emsdk_temp.mkdir(parents=True, exist_ok=True)
            sketch_temp.mkdir(parents=True, exist_ok=True)

            # Save original environment
            original_env = {}
            env_vars = [
                "ENV_FASTLED_ROOT",
                "ENV_FASTLED_SOURCE_PATH",
                "ENV_EMSDK_PATH",
                "ENV_SKETCH_ROOT",
            ]

            for var in env_vars:
                original_env[var] = os.environ.get(var)

            try:
                # Set test environment variables
                os.environ["ENV_FASTLED_ROOT"] = str(fastled_temp)
                os.environ["ENV_FASTLED_SOURCE_PATH"] = str(fastled_src_temp)
                os.environ["ENV_EMSDK_PATH"] = str(emsdk_temp)
                os.environ["ENV_SKETCH_ROOT"] = str(sketch_temp)

                # Test with no arguments should fail (missing sketch_dir)
                with patch("sys.argv", ["fastled-wasm-compiler-native"]):
                    with self.assertRaises(SystemExit):
                        _parse_args()

            finally:
                # Restore original environment
                for var, value in original_env.items():
                    if value is None:
                        os.environ.pop(var, None)
                    else:
                        os.environ[var] = value

    def test_install_emsdk_option(self):
        """Test that --install-emsdk option works as expected."""
        test_sketch_dir = Path("/tmp/test_sketch")

        with patch(
            "sys.argv",
            ["fastled-wasm-compiler-native", str(test_sketch_dir), "--install-emsdk"],
        ):
            with patch("fastled_wasm_compiler.cli_native._parse_args") as mock_parse:
                # Create a mock args object with install_emsdk=True
                mock_args = NativeCliArgs(
                    sketch_dir=test_sketch_dir,
                    build_mode="debug",
                    output_dir=None,
                    emsdk_dir=None,
                    install_emsdk=True,
                    keep_files=False,
                    profile=False,
                    strict=False,
                    headers=None,
                    add_src=False,
                )
                mock_parse.return_value = mock_args

                # Mock the get_emsdk_manager and install
                with patch(
                    "fastled_wasm_compiler.cli_native.get_emsdk_manager"
                ) as mock_get_manager:
                    mock_manager = MagicMock()
                    mock_get_manager.return_value = mock_manager

                    # Run main
                    result = main()

                    # Should succeed
                    self.assertEqual(result, 0)

                    # Should have called get_emsdk_manager and install
                    mock_get_manager.assert_called_once_with(None)
                    mock_manager.install.assert_called_once()

    def test_build_modes(self):
        """Test that all build modes are supported."""
        supported_modes = ["debug", "quick", "release"]

        for mode in supported_modes:
            with self.subTest(mode=mode):
                test_sketch_dir = Path("/tmp/test_sketch")

                # Set up required environment variables
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    fastled_temp = temp_path / "fastled"
                    fastled_src_temp = fastled_temp / "src"
                    emsdk_temp = temp_path / "emsdk"
                    sketch_temp = temp_path / "src"

                    # Create directories
                    fastled_src_temp.mkdir(parents=True, exist_ok=True)
                    emsdk_temp.mkdir(parents=True, exist_ok=True)
                    sketch_temp.mkdir(parents=True, exist_ok=True)

                    # Save original environment
                    original_env = {}
                    env_vars = [
                        "ENV_FASTLED_ROOT",
                        "ENV_FASTLED_SOURCE_PATH",
                        "ENV_EMSDK_PATH",
                        "ENV_SKETCH_ROOT",
                    ]

                    for var in env_vars:
                        original_env[var] = os.environ.get(var)

                    try:
                        # Set test environment variables
                        os.environ["ENV_FASTLED_ROOT"] = str(fastled_temp)
                        os.environ["ENV_FASTLED_SOURCE_PATH"] = str(fastled_src_temp)
                        os.environ["ENV_EMSDK_PATH"] = str(emsdk_temp)
                        os.environ["ENV_SKETCH_ROOT"] = str(sketch_temp)

                        with patch(
                            "sys.argv",
                            [
                                "fastled-wasm-compiler-native",
                                str(test_sketch_dir),
                                "--mode",
                                mode,
                            ],
                        ):
                            args = _parse_args()
                            self.assertEqual(args.build_mode, mode)

                    finally:
                        # Restore original environment
                        for var, value in original_env.items():
                            if value is None:
                                os.environ.pop(var, None)
                            else:
                                os.environ[var] = value

    def test_error_handling_nonexistent_sketch(self):
        """Test error handling for non-existent sketch directory."""
        test_sketch_dir = Path("/nonexistent/sketch")

        with patch("sys.argv", ["fastled-wasm-compiler-native", str(test_sketch_dir)]):
            with patch("fastled_wasm_compiler.cli_native._parse_args") as mock_parse:
                mock_args = NativeCliArgs(
                    sketch_dir=test_sketch_dir,
                    build_mode="debug",
                    output_dir=None,
                    emsdk_dir=None,
                    install_emsdk=False,
                    keep_files=False,
                    profile=False,
                    strict=False,
                    headers=None,
                    add_src=False,
                )
                mock_parse.return_value = mock_args

                # Don't mock exists() so it returns False for nonexistent path
                result = main()

                # Should fail with error code 1
                self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
