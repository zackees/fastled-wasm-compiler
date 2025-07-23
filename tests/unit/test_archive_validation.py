#!/usr/bin/env python3

import os
import unittest
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.compile_all_libs import ArchiveType, compile_all_libs


class TestArchiveValidation(unittest.TestCase):
    """Test archive type validation and automatic correction."""

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

    @patch("fastled_wasm_compiler.compile_all_libs._build_archives")
    def test_archive_type_validation_corrects_mismatch(
        self, mock_build_archives: MagicMock
    ) -> None:
        """Test that archive type validation corrects mismatched types."""
        # Mock successful build
        mock_build_archives.return_value = 0

        # Set environment to regular mode
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"

        # Capture print output
        import io

        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            # Try to build with THIN archive type (should be corrected to REGULAR)
            result = compile_all_libs(
                src="/test/src",
                out="/test/out",
                build_modes=["quick"],
                archive_type=ArchiveType.THIN,  # This conflicts with environment
            )

        # Check that it succeeded
        self.assertEqual(result.return_code, 0)

        # Check that warning was printed
        output = captured_output.getvalue()
        self.assertIn("WARNING: Archive type mismatch detected!", output)
        self.assertIn("Requested: thin", output)
        self.assertIn("Environment (ARCHIVE_BUILD_MODE): regular", output)
        self.assertIn("Switching to environment configuration: regular", output)

        # Verify _build_archives was called with corrected REGULAR type
        mock_build_archives.assert_called_with("quick", ArchiveType.REGULAR)

    @patch("fastled_wasm_compiler.compile_all_libs._build_archives")
    def test_archive_type_validation_no_warning_when_matching(
        self, mock_build_archives: MagicMock
    ) -> None:
        """Test that no warning is shown when archive types match."""
        # Mock successful build
        mock_build_archives.return_value = 0

        # Set environment to thin mode
        os.environ["ARCHIVE_BUILD_MODE"] = "thin"

        # Capture print output
        import io

        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            # Build with THIN archive type (matches environment)
            result = compile_all_libs(
                src="/test/src",
                out="/test/out",
                build_modes=["quick"],
                archive_type=ArchiveType.THIN,  # This matches environment
            )

        # Check that it succeeded
        self.assertEqual(result.return_code, 0)

        # Check that NO warning was printed
        output = captured_output.getvalue()
        self.assertNotIn("WARNING: Archive type mismatch detected!", output)

        # Verify _build_archives was called with the correct THIN type
        mock_build_archives.assert_called_with("quick", ArchiveType.THIN)

    @patch("fastled_wasm_compiler.compile_all_libs._build_archives")
    def test_archive_type_none_uses_environment_default(
        self, mock_build_archives: MagicMock
    ) -> None:
        """Test that passing None uses environment configuration."""
        # Mock successful build
        mock_build_archives.return_value = 0

        # Set environment to regular mode (default)
        os.environ["ARCHIVE_BUILD_MODE"] = "regular"

        # Build with None archive type (should use environment)
        result = compile_all_libs(
            src="/test/src",
            out="/test/out",
            build_modes=["quick"],
            archive_type=None,  # Should use environment default
        )

        # Check that it succeeded
        self.assertEqual(result.return_code, 0)

        # Verify _build_archives was called with REGULAR type from environment
        mock_build_archives.assert_called_with("quick", ArchiveType.REGULAR)


if __name__ == "__main__":
    unittest.main()
