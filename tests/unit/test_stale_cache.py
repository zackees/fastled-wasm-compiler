"""
Unit tests for stale file caching bug.

This test verifies that the compiler always uses fresh source files
and never compiles stale cached versions.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastled_wasm_compiler.args import Args
from fastled_wasm_compiler.run_compile import run_compile as run


class StaleCacheTest(unittest.TestCase):
    """Test that stale cached files are never used."""

    def setUp(self) -> None:
        """Set up test environment with temporary directories."""
        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.compiler_root = self.temp_dir / "compiler_root"
        self.mapped_dir = self.temp_dir / "mapped"
        self.sketch_dir = self.mapped_dir / "sketch"
        self.assets_dir = self.temp_dir / "assets"

        # Create directory structure
        self.compiler_root.mkdir(parents=True)
        self.sketch_dir.mkdir(parents=True)
        self.assets_dir.mkdir(parents=True)

        # Create required asset files (Vite dist/ output structure)
        dist_dir = self.assets_dir / "dist"
        dist_dir.mkdir()
        (dist_dir / "index.html").write_text("<html></html>")
        (dist_dir / "index.css").write_text("body {}")
        (dist_dir / "index.js").write_text("console.log('test');")

        # Create initial sketch file
        self.sketch_file = self.sketch_dir / "test.ino"
        self.initial_content = "void setup() { int x = 1; }\nvoid loop() {}"
        self.sketch_file.write_text(self.initial_content)

    def tearDown(self) -> None:
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("fastled_wasm_compiler.compile._new_compile_cmd_list")
    def test_fresh_files_always_copied_normal_build(
        self, mock_compile: MagicMock
    ) -> None:
        """Test that fresh files are always copied during normal build."""
        mock_compile.return_value = ["echo", "fake compile"]

        # First compilation with initial content
        args: Args = Args(
            compiler_root=self.compiler_root,
            assets_dirs=self.assets_dir,
            mapped_dir=self.mapped_dir,
            keep_files=True,  # Keep files to test caching
            only_copy=False,
            only_insert_header=False,
            only_compile=False,
            profile=False,
            disable_auto_clean=True,
            debug=False,
            fast_debug=False,
            quick=True,
            release=False,
            clear_ccache=False,
            strict=False,
        )

        rtn = run(args)
        self.assertEqual(0, rtn)

        # Verify initial content was processed
        sketch_tmp = self.compiler_root / "src"
        processed_file = (
            sketch_tmp / "test.ino.cpp"
        )  # .ino files get renamed to .ino.cpp
        self.assertTrue(processed_file.exists(), "Processed file should exist")

        # Now modify the source file
        new_content = "void setup() { int y = 2; }\nvoid loop() {}"
        self.sketch_file.write_text(new_content)

        # Second compilation - should use NEW content, not cached
        rtn = run(args)
        self.assertEqual(0, rtn)

        # Verify that the processed file has NEW content
        processed_content = processed_file.read_text()
        self.assertIn(
            "int y = 2",
            processed_content,
            "Processed file should contain NEW content (int y = 2)",
        )
        self.assertNotIn(
            "int x = 1",
            processed_content,
            "Processed file should NOT contain OLD content (int x = 1)",
        )

    @patch("fastled_wasm_compiler.compile._new_compile_cmd_list")
    def test_fresh_files_copied_with_only_compile_flag(
        self, mock_compile: MagicMock
    ) -> None:
        """Test that fresh files are copied even when using --only-compile flag."""
        mock_compile.return_value = ["echo", "fake compile"]

        # First, manually populate sketch_tmp with stale content
        sketch_tmp = self.compiler_root / "src"
        sketch_tmp.mkdir(parents=True, exist_ok=True)
        stale_file = sketch_tmp / "test.ino.cpp"  # Simulate already transformed file
        stale_content = "void setup() { int STALE = 999; }\nvoid loop() {}"
        stale_file.write_text(stale_content)

        # Now create fresh content in source
        fresh_content = "void setup() { int FRESH = 1; }\nvoid loop() {}"
        self.sketch_file.write_text(fresh_content)

        # Run with only_compile flag - this was the bug scenario
        args: Args = Args(
            compiler_root=self.compiler_root,
            assets_dirs=self.assets_dir,
            mapped_dir=self.mapped_dir,
            keep_files=True,
            only_copy=False,
            only_insert_header=False,
            only_compile=True,  # This flag was causing stale cache issue
            profile=False,
            disable_auto_clean=True,
            debug=False,
            fast_debug=False,
            quick=True,
            release=False,
            clear_ccache=False,
            strict=False,
        )

        rtn = run(args)
        self.assertEqual(0, rtn)

        # Verify that FRESH content was used, not STALE
        processed_content = stale_file.read_text()
        self.assertIn(
            "int FRESH = 1",
            processed_content,
            "Should use FRESH content from source, not stale cache",
        )
        self.assertNotIn(
            "int STALE = 999",
            processed_content,
            "Should NOT use STALE cached content",
        )

    @patch("fastled_wasm_compiler.compile._new_compile_cmd_list")
    def test_sketch_tmp_cleaned_before_copy(self, mock_compile: MagicMock) -> None:
        """Test that sketch_tmp directory is cleaned before copying fresh files."""
        mock_compile.return_value = ["echo", "fake compile"]

        # Create stale files in sketch_tmp
        sketch_tmp = self.compiler_root / "src"
        sketch_tmp.mkdir(parents=True, exist_ok=True)
        stale_file1 = sketch_tmp / "old_file.cpp"
        stale_file2 = sketch_tmp / "another_old_file.h"
        stale_file1.write_text("// OLD content 1")
        stale_file2.write_text("// OLD content 2")

        # Create fresh source file
        self.sketch_file.write_text("void setup() {}\nvoid loop() {}")

        # Run compilation
        args: Args = Args(
            compiler_root=self.compiler_root,
            assets_dirs=self.assets_dir,
            mapped_dir=self.mapped_dir,
            keep_files=True,
            only_copy=False,
            only_insert_header=False,
            only_compile=False,
            profile=False,
            disable_auto_clean=True,
            debug=False,
            fast_debug=False,
            quick=True,
            release=False,
            clear_ccache=False,
            strict=False,
        )

        rtn = run(args)
        self.assertEqual(0, rtn)

        # Verify stale files were removed
        self.assertFalse(
            stale_file1.exists(),
            "Stale file old_file.cpp should have been removed",
        )
        self.assertFalse(
            stale_file2.exists(),
            "Stale file another_old_file.h should have been removed",
        )

        # Verify only fresh file exists
        processed_file = (
            sketch_tmp / "test.ino.cpp"
        )  # .ino files get renamed to .ino.cpp
        self.assertTrue(processed_file.exists(), "Fresh file should exist")


if __name__ == "__main__":
    unittest.main()
