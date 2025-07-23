#!/usr/bin/env python3

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastled_wasm_compiler.paths import (
    get_archive_build_mode,
    get_expected_archive_path,
    get_fastled_library_path,
    validate_archive_configuration,
)


class TestExclusiveArchiveModes(unittest.TestCase):
    """Test exclusive archive mode functionality."""

    def setUp(self):
        """Set up test environment."""
        # Clear any existing environment variables
        for env_var in [
            "ARCHIVE_BUILD_MODE",
            "NO_THIN_LTO",
        ]:
            if env_var in os.environ:
                del os.environ[env_var]

    def tearDown(self):
        """Clean up test environment."""
        # Clear any test environment variables
        for env_var in [
            "ARCHIVE_BUILD_MODE",
            "NO_THIN_LTO",
        ]:
            if env_var in os.environ:
                del os.environ[env_var]

    def test_get_archive_build_mode_default(self):
        """Test that default mode is 'regular' (best performance)."""
        mode = get_archive_build_mode()
        self.assertEqual(mode, "regular")

    def test_get_archive_build_mode_thin_only(self):
        """Test thin archives only mode."""
        os.environ["ARCHIVE_BUILD_MODE"] = "thin"
        mode = get_archive_build_mode()
        self.assertEqual(mode, "thin")

    def test_get_archive_build_mode_regular_only(self):
        """Test regular archives only mode."""
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"
        mode = get_archive_build_mode()
        self.assertEqual(mode, "regular")

    def test_get_archive_build_mode_case_insensitive(self):
        """Test that archive mode is case insensitive."""
        os.environ["ARCHIVE_BUILD_MODE"] = "THIN"
        mode = get_archive_build_mode()
        self.assertEqual(mode, "thin")

        os.environ["ARCHIVE_BUILD_MODE"] = "Regular"
        mode = get_archive_build_mode()
        self.assertEqual(mode, "regular")

    def test_get_archive_build_mode_invalid_value(self):
        """Test that invalid values default to 'regular'."""
        os.environ["ARCHIVE_BUILD_MODE"] = "invalid"
        mode = get_archive_build_mode()
        self.assertEqual(mode, "regular")

    def test_get_expected_archive_path_thin_only(self):
        """Test expected path for thin archives only mode."""
        os.environ["ARCHIVE_BUILD_MODE"] = "thin"

        with patch("fastled_wasm_compiler.paths.BUILD_ROOT", Path("/build")):
            path = get_expected_archive_path("DEBUG")
            self.assertEqual(path, Path("/build/debug/libfastled-thin.a"))

            path = get_expected_archive_path("QUICK")
            self.assertEqual(path, Path("/build/quick/libfastled-thin.a"))

    def test_get_expected_archive_path_regular_only(self):
        """Test expected path for regular archives only mode."""
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"

        with patch("fastled_wasm_compiler.paths.BUILD_ROOT", Path("/build")):
            path = get_expected_archive_path("DEBUG")
            self.assertEqual(path, Path("/build/debug/libfastled.a"))

            path = get_expected_archive_path("RELEASE")
            self.assertEqual(path, Path("/build/release/libfastled.a"))

    def test_validate_archive_configuration_valid_thin_only(self):
        """Test validation passes for valid thin only configuration."""
        os.environ["ARCHIVE_BUILD_MODE"] = "thin"
        os.environ["NO_THIN_LTO"] = "0"

        # Should not raise
        validate_archive_configuration()

    def test_validate_archive_configuration_valid_regular_only(self):
        """Test validation passes for valid regular only configuration."""
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"
        os.environ["NO_THIN_LTO"] = "1"

        # Should not raise
        validate_archive_configuration()

    def test_validate_archive_configuration_invalid_thin_only(self):
        """Test validation fails for invalid thin only configuration."""
        os.environ["ARCHIVE_BUILD_MODE"] = "thin"
        os.environ["NO_THIN_LTO"] = "1"

        with self.assertRaises(RuntimeError) as cm:
            validate_archive_configuration()

        self.assertIn("ARCHIVE_BUILD_MODE=thin but NO_THIN_LTO=1", str(cm.exception))

    def test_validate_archive_configuration_invalid_regular_only(self):
        """Test validation fails for invalid regular only configuration."""
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"
        os.environ["NO_THIN_LTO"] = "0"

        with self.assertRaises(RuntimeError) as cm:
            validate_archive_configuration()

        self.assertIn("ARCHIVE_BUILD_MODE=regular but NO_THIN_LTO=0", str(cm.exception))

    def test_get_fastled_library_path_missing_file(self):
        """Test error handling when library file doesn't exist."""
        os.environ["ARCHIVE_BUILD_MODE"] = "thin"

        with patch("fastled_wasm_compiler.paths.BUILD_ROOT", Path("/nonexistent")):
            with self.assertRaises(RuntimeError) as cm:
                get_fastled_library_path("DEBUG")

            error_msg = str(cm.exception)
            self.assertIn("Required FastLED library not found", error_msg)
            self.assertIn("thin archive", error_msg)
            self.assertIn("thin", error_msg)

    @patch("fastled_wasm_compiler.paths.BUILD_ROOT", Path("/build"))
    def test_get_fastled_library_path_existing_file(self):
        """Test successful path retrieval when file exists."""
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"

        # Mock the file existence check
        with patch.object(Path, "exists", return_value=True):
            path = get_fastled_library_path("QUICK")
            self.assertEqual(path, Path("/build/quick/libfastled.a"))


if __name__ == "__main__":
    unittest.main()
