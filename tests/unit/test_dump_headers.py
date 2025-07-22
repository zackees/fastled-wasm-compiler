"""
Unit tests for header dumping functionality.
"""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from fastled_wasm_compiler.dump_headers import HeaderDumper, dump_headers


class TestHeaderDumper:
    """Test cases for HeaderDumper class."""

    @patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager")
    @patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed")
    def test_init_directory_output(
        self, mock_ensure_fastled: MagicMock, mock_get_emsdk: MagicMock
    ):
        """Test HeaderDumper initialization for directory output."""
        mock_fastled_src = Path("/mock/fastled/src")
        mock_ensure_fastled.return_value = mock_fastled_src

        mock_emsdk_manager = Mock()
        mock_get_emsdk.return_value = mock_emsdk_manager

        output_dir = Path("/tmp/headers")
        dumper = HeaderDumper(output_dir)

        assert dumper.output_dir == output_dir
        assert dumper.is_zip_output is False
        assert dumper.fastled_src == mock_fastled_src
        assert dumper.emsdk_manager == mock_emsdk_manager

    @patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager")
    @patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed")
    def test_init_zip_output(
        self, mock_ensure_fastled: MagicMock, mock_get_emsdk: MagicMock
    ):
        """Test HeaderDumper initialization for zip output."""
        mock_fastled_src = Path("/mock/fastled/src")
        mock_ensure_fastled.return_value = mock_fastled_src

        mock_emsdk_manager = Mock()
        mock_get_emsdk.return_value = mock_emsdk_manager

        output_zip = Path("/tmp/headers.zip")
        dumper = HeaderDumper(output_zip)

        assert dumper.output_dir == output_zip
        assert dumper.is_zip_output is True

    def test_header_extensions(self):
        """Test that correct header extensions are defined."""
        expected_extensions = [".h", ".hpp", ".hh", ".hxx"]
        assert HeaderDumper.HEADER_EXTENSIONS == expected_extensions

    def test_exclude_patterns(self):
        """Test that correct exclude patterns are defined."""
        expected_patterns = ["*.gch", "*.pch", "*.bak", "*~", ".*"]
        assert HeaderDumper.EXCLUDE_PATTERNS == expected_patterns

    def test_should_exclude_file(self):
        """Test file exclusion logic."""
        output_dir = Path("/tmp/headers")

        with (
            patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager"),
            patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed"),
        ):
            dumper = HeaderDumper(output_dir)

        # Test exclude patterns
        assert dumper._should_exclude_file(Path("/tmp/test.gch")) is True
        assert dumper._should_exclude_file(Path("/tmp/test.pch")) is True
        assert dumper._should_exclude_file(Path("/tmp/test.bak")) is True
        assert dumper._should_exclude_file(Path("/tmp/test~")) is True
        assert dumper._should_exclude_file(Path("/tmp/.hidden")) is True

        # Test allowed files
        assert dumper._should_exclude_file(Path("/tmp/test.h")) is False
        assert dumper._should_exclude_file(Path("/tmp/test.hpp")) is False

    def test_is_platform_header(self):
        """Test platform header detection."""
        output_dir = Path("/tmp/headers")

        with (
            patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager"),
            patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed"),
        ):
            dumper = HeaderDumper(output_dir)

        assert dumper._is_platform_header(Path("platforms/wasm/test.h")) is True
        assert dumper._is_platform_header(Path("core/test.h")) is False
        assert dumper._is_platform_header(Path("test.h")) is False

    def test_is_allowed_platform_path(self):
        """Test allowed platform path logic."""
        output_dir = Path("/tmp/headers")

        with (
            patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager"),
            patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed"),
        ):
            dumper = HeaderDumper(output_dir)

        # Allowed platform subdirectories
        assert (
            dumper._is_allowed_platform_path(Path("/src/platforms/wasm/test.h")) is True
        )
        assert (
            dumper._is_allowed_platform_path(Path("/src/platforms/shared/test.h"))
            is True
        )
        assert (
            dumper._is_allowed_platform_path(Path("/src/platforms/stub/test.h")) is True
        )
        assert (
            dumper._is_allowed_platform_path(Path("/src/platforms/posix/test.h"))
            is True
        )

        # Disallowed platform subdirectories
        assert (
            dumper._is_allowed_platform_path(Path("/src/platforms/arduino/test.h"))
            is False
        )
        assert (
            dumper._is_allowed_platform_path(Path("/src/platforms/esp32/test.h"))
            is False
        )

        # Files directly in platforms directory (allowed)
        assert dumper._is_allowed_platform_path(Path("/src/platforms/test.h")) is True

        # Non-platform files (allowed)
        assert dumper._is_allowed_platform_path(Path("/src/core/test.h")) is True


class TestZipFunctionality:
    """Test cases for zip archive functionality."""

    @patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager")
    @patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed")
    def test_zip_creation(
        self, mock_ensure_fastled: MagicMock, mock_get_emsdk: MagicMock
    ):
        """Test that zip archives are created correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a mock source directory with some test files
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create test files
            (source_dir / "test1.h").write_text("#include <stdio.h>")
            (source_dir / "test2.hpp").write_text("class Test {};")
            (source_dir / "subdir").mkdir()
            (source_dir / "subdir" / "test3.h").write_text("#define TEST 1")

            # Create zip path
            zip_path = temp_path / "test.zip"

            # Mock dependencies
            mock_ensure_fastled.return_value = source_dir
            mock_emsdk_manager = Mock()
            mock_emsdk_manager.emsdk_dir = Path("/mock/emsdk")
            mock_get_emsdk.return_value = mock_emsdk_manager

            dumper = HeaderDumper(zip_path)
            dumper._create_zip_archive(source_dir, zip_path)

            # Verify zip file was created
            assert zip_path.exists()
            assert zip_path.stat().st_size > 0

            # Verify zip contents
            with zipfile.ZipFile(zip_path, "r") as zipf:
                file_list = zipf.namelist()
                assert "test1.h" in file_list
                assert "test2.hpp" in file_list
                assert "subdir/test3.h" in file_list

    @patch("fastled_wasm_compiler.dump_headers.get_emsdk_manager")
    @patch("fastled_wasm_compiler.dump_headers.ensure_fastled_installed")
    def test_dump_headers_to_zip(
        self, mock_ensure_fastled: MagicMock, mock_get_emsdk: MagicMock
    ):
        """Test full header dumping to zip archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create mock FastLED source with headers in src/ subdirectory
            fastled_src = temp_path / "fastled_src"
            fastled_src_dir = fastled_src / "src"
            fastled_src_dir.mkdir(parents=True)
            (fastled_src_dir / "FastLED.h").write_text("#pragma once")
            (fastled_src_dir / "CRGB.h").write_text("class CRGB {};")

            # Create mock EMSDK
            emsdk_dir = temp_path / "emsdk"
            sysroot_include = (
                emsdk_dir / "upstream" / "emscripten" / "cache" / "sysroot" / "include"
            )
            sysroot_include.mkdir(parents=True)
            (sysroot_include / "stdio.h").write_text("#include <stddef.h>")

            # Create Arduino compatibility headers
            arduino_dir = fastled_src / "platforms" / "wasm" / "compiler"
            arduino_dir.mkdir(parents=True)
            (arduino_dir / "Arduino.h").write_text("#pragma once")

            # Mock dependencies
            mock_ensure_fastled.return_value = fastled_src
            mock_emsdk_manager = Mock()
            mock_emsdk_manager.emsdk_dir = emsdk_dir
            mock_emsdk_manager.is_installed.return_value = True
            mock_get_emsdk.return_value = mock_emsdk_manager

            # Test zip output
            zip_path = temp_path / "headers.zip"
            dumper = HeaderDumper(zip_path)

            manifest = dumper.dump_all_headers()

            # Verify zip was created
            assert zip_path.exists()

            # Verify manifest structure
            assert "fastled" in manifest
            assert "wasm" in manifest
            assert "arduino" in manifest
            assert "metadata" in manifest

            # Verify zip contents
            with zipfile.ZipFile(zip_path, "r") as zipf:
                file_list = zipf.namelist()
                assert "manifest.json" in file_list
                assert any("fastled/src/" in f for f in file_list)
                assert any("wasm/" in f for f in file_list)
                assert any("arduino/" in f for f in file_list)


class TestConvenienceFunction:
    """Test cases for the convenience function."""

    @patch("fastled_wasm_compiler.dump_headers.HeaderDumper")
    def test_dump_headers_function(self, mock_dumper_class: MagicMock):
        """Test the convenience dump_headers function."""
        mock_dumper = Mock()
        mock_manifest = {"test": "manifest"}
        mock_dumper.dump_all_headers.return_value = mock_manifest
        mock_dumper_class.return_value = mock_dumper

        output_dir = Path("/tmp/headers")
        result = dump_headers(output_dir)

        mock_dumper_class.assert_called_once_with(output_dir, False)
        mock_dumper.dump_all_headers.assert_called_once()
        assert result == mock_manifest


class TestDumpHeadersToZip:
    """Test cases for the dump_headers_to_zip programmatic function."""

    @patch("fastled_wasm_compiler.dump_headers.HeaderDumper")
    def test_dump_headers_to_zip_with_zip_extension(self, mock_dumper_class: MagicMock):
        """Test dump_headers_to_zip with a path that already has .zip extension."""
        from fastled_wasm_compiler.dump_headers import dump_headers_to_zip

        mock_dumper = Mock()
        mock_manifest = {"test": "manifest", "metadata": {"total_files": 42}}
        mock_dumper.dump_all_headers.return_value = mock_manifest
        mock_dumper_class.return_value = mock_dumper

        zip_path = Path("/tmp/headers.zip")
        result = dump_headers_to_zip(zip_path)

        mock_dumper_class.assert_called_once_with(zip_path, False)
        mock_dumper.dump_all_headers.assert_called_once()
        assert result == mock_manifest

    @patch("fastled_wasm_compiler.dump_headers.HeaderDumper")
    def test_dump_headers_to_zip_without_zip_extension(
        self, mock_dumper_class: MagicMock
    ):
        """Test dump_headers_to_zip with a path that doesn't have .zip extension - should add it."""
        from fastled_wasm_compiler.dump_headers import dump_headers_to_zip

        mock_dumper = Mock()
        mock_manifest = {"test": "manifest", "metadata": {"total_files": 42}}
        mock_dumper.dump_all_headers.return_value = mock_manifest
        mock_dumper_class.return_value = mock_dumper

        # Path without .zip extension
        zip_path = Path("/tmp/headers")
        result = dump_headers_to_zip(zip_path)

        # Should be called with .zip extension added
        expected_path = Path("/tmp/headers.zip")
        mock_dumper_class.assert_called_once_with(expected_path, False)
        mock_dumper.dump_all_headers.assert_called_once()
        assert result == mock_manifest

    @patch("fastled_wasm_compiler.dump_headers.HeaderDumper")
    def test_dump_headers_to_zip_with_different_extension(
        self, mock_dumper_class: MagicMock
    ):
        """Test dump_headers_to_zip with a different extension - should replace with .zip."""
        from fastled_wasm_compiler.dump_headers import dump_headers_to_zip

        mock_dumper = Mock()
        mock_manifest = {"test": "manifest", "metadata": {"total_files": 42}}
        mock_dumper.dump_all_headers.return_value = mock_manifest
        mock_dumper_class.return_value = mock_dumper

        # Path with different extension
        zip_path = Path("/tmp/headers.tar.gz")
        result = dump_headers_to_zip(zip_path)

        # Should replace extension with .zip
        expected_path = Path("/tmp/headers.tar.zip")
        mock_dumper_class.assert_called_once_with(expected_path, False)
        mock_dumper.dump_all_headers.assert_called_once()
        assert result == mock_manifest

    @patch("fastled_wasm_compiler.dump_headers.HeaderDumper")
    def test_dump_headers_to_zip_with_include_source(
        self, mock_dumper_class: MagicMock
    ):
        """Test dump_headers_to_zip with include_source=True."""
        from fastled_wasm_compiler.dump_headers import dump_headers_to_zip

        mock_dumper = Mock()
        mock_manifest = {"test": "manifest", "metadata": {"total_files": 42}}
        mock_dumper.dump_all_headers.return_value = mock_manifest
        mock_dumper_class.return_value = mock_dumper

        zip_path = Path("/tmp/headers.zip")
        result = dump_headers_to_zip(zip_path, include_source=True)

        mock_dumper_class.assert_called_once_with(zip_path, True)
        mock_dumper.dump_all_headers.assert_called_once()
        assert result == mock_manifest

    @patch("fastled_wasm_compiler.dump_headers.HeaderDumper")
    def test_dump_headers_to_zip_case_insensitive_extension(
        self, mock_dumper_class: MagicMock
    ):
        """Test dump_headers_to_zip with uppercase .ZIP extension."""
        from fastled_wasm_compiler.dump_headers import dump_headers_to_zip

        mock_dumper = Mock()
        mock_manifest = {"test": "manifest", "metadata": {"total_files": 42}}
        mock_dumper.dump_all_headers.return_value = mock_manifest
        mock_dumper_class.return_value = mock_dumper

        # Path with uppercase .ZIP extension
        zip_path = Path("/tmp/headers.ZIP")
        result = dump_headers_to_zip(zip_path)

        # Should not modify the case, just check it's recognized as zip
        mock_dumper_class.assert_called_once_with(zip_path, False)
        mock_dumper.dump_all_headers.assert_called_once()
        assert result == mock_manifest


if __name__ == "__main__":
    pytest.main([__file__])
