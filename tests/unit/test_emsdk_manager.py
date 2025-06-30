"""
Unit tests for EMSDK Manager

Tests the migration from Docker-based EMSDK to platform-specific pre-built binaries.
These tests validate:
- Platform detection
- Binary download and installation
- Environment setup
- Tool path resolution
- Basic compilation functionality
"""

import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastled_wasm_compiler.emsdk_manager import (
    EmsdkManager,
    EmsdkPlatform,
    get_emsdk_manager,
)


class TestEmsdkPlatform(unittest.TestCase):
    """Test EmsdkPlatform data class."""

    def test_platform_creation(self):
        """Test creating platform info."""
        platform_info = EmsdkPlatform(
            "ubuntu-latest", "Ubuntu Linux", "emsdk-ubuntu-latest", "ubuntu"
        )

        self.assertEqual(platform_info.name, "ubuntu-latest")
        self.assertEqual(platform_info.display_name, "Ubuntu Linux")
        self.assertEqual(platform_info.archive_pattern, "emsdk-ubuntu-latest")
        self.assertEqual(platform_info.platform_name, "ubuntu")


class TestEmsdkManager(unittest.TestCase):
    """Test EMSDK Manager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_dir = self.temp_dir / "cache"
        self.manager = EmsdkManager(install_dir=self.temp_dir, cache_dir=self.cache_dir)

    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_platform_detection_linux(self):
        """Test platform detection for Linux."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
        ):

            manager = EmsdkManager(install_dir=self.temp_dir)
            platform_info = manager.platform_info

            self.assertEqual(platform_info.name, "ubuntu-latest")
            self.assertEqual(platform_info.display_name, "Ubuntu Linux")
            self.assertEqual(platform_info.archive_pattern, "emsdk-ubuntu-latest")

    def test_platform_detection_macos_arm(self):
        """Test platform detection for macOS ARM."""
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="arm64"),
        ):

            manager = EmsdkManager(install_dir=self.temp_dir)
            platform_info = manager.platform_info

            self.assertEqual(platform_info.name, "macos-arm64")
            self.assertEqual(platform_info.display_name, "macOS Apple Silicon")
            self.assertEqual(platform_info.archive_pattern, "emsdk-macos-arm64")

    def test_platform_detection_macos_intel(self):
        """Test platform detection for macOS Intel."""
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="x86_64"),
        ):

            manager = EmsdkManager(install_dir=self.temp_dir)
            platform_info = manager.platform_info

            self.assertEqual(platform_info.name, "macos-x86_64")
            self.assertEqual(platform_info.display_name, "macOS Intel")
            self.assertEqual(platform_info.archive_pattern, "emsdk-macos-x86_64")

    def test_platform_detection_windows(self):
        """Test platform detection for Windows."""
        with (
            patch("platform.system", return_value="Windows"),
            patch("platform.machine", return_value="AMD64"),
        ):

            manager = EmsdkManager(install_dir=self.temp_dir)
            platform_info = manager.platform_info

            self.assertEqual(platform_info.name, "windows-latest")
            self.assertEqual(platform_info.display_name, "Windows")
            self.assertEqual(platform_info.archive_pattern, "emsdk-windows-latest")

    def test_platform_detection_unsupported(self):
        """Test platform detection for unsupported platform."""
        with (
            patch("platform.system", return_value="FreeBSD"),
            patch("platform.machine", return_value="x86_64"),
        ):

            with self.assertRaises(RuntimeError) as cm:
                EmsdkManager(install_dir=self.temp_dir)

            self.assertIn("Unsupported platform FreeBSD-x86_64", str(cm.exception))

    def test_is_installed_false_missing_dir(self):
        """Test is_installed returns False when directory doesn't exist."""
        self.assertFalse(self.manager.is_installed())

    def test_is_installed_false_missing_files(self):
        """Test is_installed returns False when key files missing."""
        # Create emsdk directory but not key files
        self.manager.emsdk_dir.mkdir(parents=True)
        self.assertFalse(self.manager.is_installed())

    def test_is_installed_true(self):
        """Test is_installed returns True when properly installed."""
        # Create required directory structure and files
        emsdk_dir = self.manager.emsdk_dir
        emsdk_dir.mkdir(parents=True)

        # Create emsdk_env.sh
        (emsdk_dir / "emsdk_env.sh").touch()

        # Create emcc
        emcc_dir = emsdk_dir / "upstream" / "emscripten"
        emcc_dir.mkdir(parents=True)
        (emcc_dir / "emcc").touch()

        self.assertTrue(self.manager.is_installed())

    @patch("httpx.stream")
    def test_download_file(self, mock_stream):
        """Test file download functionality."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_bytes.return_value = [b"test content"]
        mock_stream.return_value.__enter__.return_value = mock_response

        test_file = self.temp_dir / "test.txt"
        self.manager._download_file("http://example.com/test.txt", test_file)

        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_bytes(), b"test content")

    def test_reconstruct_archive_manual(self):
        """Test manual archive reconstruction."""
        download_dir = self.temp_dir / "download"
        download_dir.mkdir()

        # Create mock part files
        base_pattern = "emsdk-test"
        part1 = download_dir / f"{base_pattern}.tar.xz.partaa"
        part2 = download_dir / f"{base_pattern}.tar.xz.partab"

        part1.write_bytes(b"part1content")
        part2.write_bytes(b"part2content")

        # Reconstruct
        result = self.manager._reconstruct_archive(download_dir, base_pattern)

        # Check result
        expected_path = download_dir / f"{base_pattern}.tar.xz"
        self.assertEqual(result, expected_path)
        self.assertTrue(expected_path.exists())
        self.assertEqual(expected_path.read_bytes(), b"part1contentpart2content")

    def test_reconstruct_archive_with_script(self):
        """Test archive reconstruction using provided script."""
        # Skip this test on Windows due to bash script execution issues
        if platform.system() == "Windows":
            self.skipTest(
                "Bash script execution not reliable on Windows in test environment"
            )

        download_dir = self.temp_dir / "download"
        download_dir.mkdir()

        base_pattern = "emsdk-test"
        target_archive = download_dir / f"{base_pattern}.tar.xz"
        reconstruct_script = download_dir / f"{base_pattern}-reconstruct.sh"

        # Create mock reconstruction script
        script_content = f"""#!/bin/bash
echo "test archive content" > {target_archive}
"""
        reconstruct_script.write_text(script_content)
        reconstruct_script.chmod(0o755)

        # Reconstruct
        result = self.manager._reconstruct_archive(download_dir, base_pattern)

        # Check result
        self.assertEqual(result, target_archive)
        self.assertTrue(target_archive.exists())
        self.assertIn("test archive content", target_archive.read_text())

    def test_get_tool_paths_not_installed(self):
        """Test get_tool_paths raises error when not installed."""
        with self.assertRaises(RuntimeError) as cm:
            self.manager.get_tool_paths()

        self.assertIn("EMSDK not installed", str(cm.exception))

    def test_get_tool_paths_installed(self):
        """Test get_tool_paths returns correct paths when installed."""
        # Install EMSDK if not already installed
        if not self.manager.is_installed():
            self.manager.install()

        # Get tool paths
        tool_paths = self.manager.get_tool_paths()

        # Verify paths
        tools = ["emcc", "em++", "emar", "emranlib"]
        self.assertEqual(len(tool_paths), 4)
        for tool in tools:
            self.assertIn(tool, tool_paths)
            self.assertTrue(
                tool_paths[tool].exists(),
                f"Tool {tool} not found at {tool_paths[tool]}",
            )

    def test_get_tool_paths_windows_extensions(self):
        """Test get_tool_paths adds .bat extension on Windows."""
        with patch("platform.system", return_value="Windows"):
            # Set up mock installation
            emsdk_dir = self.manager.emsdk_dir
            upstream_dir = emsdk_dir / "upstream" / "emscripten"
            upstream_dir.mkdir(parents=True)

            # Create emsdk_env.sh
            (emsdk_dir / "emsdk_env.sh").touch()

            # Create tool files with .bat extension
            tools = ["emcc", "em++", "emar", "emranlib"]
            for tool in tools:
                (upstream_dir / f"{tool}.bat").touch()

            # Mock is_installed to return True
            with patch.object(self.manager, "is_installed", return_value=True):
                # Get tool paths
                tool_paths = self.manager.get_tool_paths()

                # Verify .bat extensions
                for tool in tools:
                    self.assertTrue(tool_paths[tool].name.endswith(".bat"))

    def test_get_env_vars(self):
        """Test getting environment variables from emsdk_env.sh."""
        # Install EMSDK if not already installed
        if not self.manager.is_installed():
            self.manager.install()

        # Get environment variables
        env_vars = self.manager.get_env_vars()

        # Verify important environment variables exist
        self.assertIn("EMSDK", env_vars)
        self.assertIn("PATH", env_vars)

        # Verify EMSDK path points to our installation
        self.assertEqual(env_vars["EMSDK"], str(self.manager.emsdk_dir))

    def test_create_wrapper_scripts_unix(self):
        """Test creating wrapper scripts on Unix-like systems."""
        with patch("platform.system", return_value="Linux"):
            # Set up mock installation
            self._setup_mock_installation()

            # Create wrapper scripts
            wrapper_dir = self.temp_dir / "wrappers"
            scripts = self.manager.create_wrapper_scripts(wrapper_dir)

            # Check emcc wrapper
            self.assertIn("ccache-emcc", scripts)
            emcc_wrapper = scripts["ccache-emcc"]
            self.assertTrue(emcc_wrapper.exists())
            self.assertTrue(emcc_wrapper.name.endswith(".sh"))

            content = emcc_wrapper.read_text()
            self.assertIn("ccache", content)
            self.assertIn("emcc", content)

    def test_create_wrapper_scripts_windows(self):
        """Test creating wrapper scripts on Windows."""
        with patch("platform.system", return_value="Windows"):
            # Set up mock installation
            self._setup_mock_installation(windows=True)

            # Mock is_installed to return True
            with patch.object(self.manager, "is_installed", return_value=True):
                # Create wrapper scripts
                wrapper_dir = self.temp_dir / "wrappers"
                scripts = self.manager.create_wrapper_scripts(wrapper_dir)

                # Check emcc wrapper
                self.assertIn("ccache-emcc", scripts)
                emcc_wrapper = scripts["ccache-emcc"]
                self.assertTrue(emcc_wrapper.exists())
                self.assertTrue(emcc_wrapper.name.endswith(".bat"))

                content = emcc_wrapper.read_text()
                self.assertIn("ccache", content)
                self.assertIn("emcc", content)

    def _setup_mock_installation(self, windows=False):
        """Helper to set up a mock EMSDK installation."""
        emsdk_dir = self.manager.emsdk_dir
        upstream_dir = emsdk_dir / "upstream" / "emscripten"
        upstream_dir.mkdir(parents=True)

        # Create emsdk_env.sh
        (emsdk_dir / "emsdk_env.sh").touch()

        # Create tool files
        tools = ["emcc", "em++", "emar", "emranlib"]
        for tool in tools:
            if windows:
                (upstream_dir / f"{tool}.bat").touch()
            else:
                (upstream_dir / tool).touch()


class TestEmsdkManagerIntegration(unittest.TestCase):
    """Integration tests for EMSDK Manager.

    These tests require an actual EMSDK installation and are more expensive.
    They are only run when explicitly enabled.
    """

    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = EmsdkManager(install_dir=self.temp_dir)

        # Skip if integration tests not enabled
        if not os.environ.get("RUN_INTEGRATION_TESTS"):
            self.skipTest("Integration tests not enabled. Set RUN_INTEGRATION_TESTS=1")

    def tearDown(self):
        """Clean up integration test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_installation(self):
        """Test full EMSDK installation and setup."""
        # This test actually downloads and installs EMSDK
        self.manager.install()

        # Verify installation
        self.assertTrue(self.manager.is_installed())

        # Test tool paths
        tool_paths = self.manager.get_tool_paths()
        self.assertIn("emcc", tool_paths)
        self.assertTrue(tool_paths["emcc"].exists())

        # Test environment setup
        env_vars = self.manager.setup_environment()
        self.assertIn("EMSDK", env_vars)
        self.assertIn("PATH", env_vars)

    def test_compilation_smoke_test(self):
        """Test basic compilation with installed EMSDK."""
        # Install EMSDK
        self.manager.install()

        # Create a simple test program
        test_c = self.temp_dir / "test.c"
        test_c.write_text(
            """
#include <stdio.h>
int main() {
    printf("Hello from EMSDK!\\n");
    return 0;
}
"""
        )

        # Get tool paths and environment
        tool_paths = self.manager.get_tool_paths()
        env_vars = self.manager.setup_environment()

        # Compile test program
        cmd = [
            str(tool_paths["emcc"]),
            str(test_c),
            "-o",
            str(self.temp_dir / "test.js"),
        ]

        result = subprocess.run(
            cmd, cwd=self.temp_dir, env=env_vars, capture_output=True, text=True
        )

        # Check compilation succeeded
        self.assertEqual(result.returncode, 0, f"Compilation failed: {result.stderr}")

        # Check output files exist
        self.assertTrue((self.temp_dir / "test.js").exists())
        self.assertTrue((self.temp_dir / "test.wasm").exists())


class TestEmsdkManagerFactory(unittest.TestCase):
    """Test EMSDK Manager factory function."""

    def test_get_emsdk_manager_default(self):
        """Test getting EMSDK manager with default settings."""
        manager = get_emsdk_manager()

        self.assertIsInstance(manager, EmsdkManager)
        self.assertEqual(manager.install_dir, Path.home() / ".fastled-emsdk")
        self.assertEqual(manager.cache_dir, Path.cwd() / ".cache" / "emsdk-binaries")

    def test_get_emsdk_manager_custom_dirs(self):
        """Test getting EMSDK manager with custom directories."""
        custom_install = Path("/tmp/custom-emsdk")
        custom_cache = Path("/tmp/custom-cache")
        manager = get_emsdk_manager(install_dir=custom_install, cache_dir=custom_cache)

        self.assertIsInstance(manager, EmsdkManager)
        self.assertEqual(manager.install_dir, custom_install)
        self.assertEqual(manager.cache_dir, custom_cache)


if __name__ == "__main__":
    # Run tests
    unittest.main()
