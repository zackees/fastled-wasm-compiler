"""
Integration tests for EMSDK Manager

These tests require actual EMSDK binary downloads and installation.
They are expensive and should only be run when explicitly needed.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastled_wasm_compiler.emsdk_manager import EmsdkManager


class TestEmsdkManagerIntegration(unittest.TestCase):
    """Integration tests for EMSDK Manager.

    These tests require an actual EMSDK installation and are more expensive.
    They are only run when explicitly enabled.
    """

    @classmethod
    def setUpClass(cls):
        """Set up shared cache for all integration tests."""
        # Use a persistent cache directory to speed up multiple test runs
        cls.shared_cache_dir = Path.cwd() / ".cache" / "test-emsdk-binaries"
        cls.shared_cache_dir.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        # Use shared cache but separate install directory for each test
        self.manager = EmsdkManager(
            install_dir=self.temp_dir, cache_dir=self.shared_cache_dir
        )

        # Skip if integration tests not enabled
        if not os.environ.get("RUN_INTEGRATION_TESTS"):
            self.skipTest("Integration tests not enabled. Set RUN_INTEGRATION_TESTS=1")

    def tearDown(self):
        """Clean up integration test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Note: We don't clean up shared_cache_dir to preserve downloads

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
        env_vars = self.manager.get_env_vars()
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
        env_vars = self.manager.get_env_vars()

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

    def test_cache_functionality(self):
        """Test that downloaded binaries are properly cached."""
        # First installation should download
        start_time = os.times()
        self.manager.install()
        first_install_time = os.times()[0] - start_time[0]

        # Clean up installation but keep cache
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = EmsdkManager(
            install_dir=self.temp_dir, cache_dir=self.shared_cache_dir
        )

        # Second installation should use cache
        start_time = os.times()
        self.manager.install()
        second_install_time = os.times()[0] - start_time[0]

        # Verify installation still works
        self.assertTrue(self.manager.is_installed())

        # Second installation should be significantly faster
        # (cache hit vs download)
        self.assertLess(second_install_time, first_install_time * 0.5)


if __name__ == "__main__":
    unittest.main()
