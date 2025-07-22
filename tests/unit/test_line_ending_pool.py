"""
Unit tests for the line_ending_pool module.

Tests the essential functionality of LineEndingProcessPool and worker functions.
"""

import tempfile
import unittest
from pathlib import Path

from fastled_wasm_compiler.line_ending_pool import (
    LineEndingProcessPool,
    _line_ending_worker,
    get_line_ending_pool,
    shutdown_global_pool,
)


class TestLineEndingPool(unittest.TestCase):
    """Test the core line ending pool functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_complete_line_ending_functionality(self):
        """Test complete line ending conversion workflow."""
        pool = LineEndingProcessPool(max_workers=2)

        try:
            # Test 1: Text file with line ending conversion
            src_file = self.temp_path / "text.txt"
            dst_file = self.temp_path / "text_out.txt"

            # Create file with Windows line endings
            src_file.write_bytes(b"line1\r\nline2\r\nline3\r\n")

            # Test worker function directly
            result = _line_ending_worker(str(src_file), str(dst_file))
            self.assertTrue(result)  # Should be different/updated

            # Check conversion worked
            dst_content = dst_file.read_bytes()
            self.assertEqual(dst_content, b"line1\nline2\nline3\n")

            # Test 2: Pool synchronous processing
            src_file2 = self.temp_path / "sync.txt"
            dst_file2 = self.temp_path / "sync_out.txt"
            src_file2.write_bytes(b"sync test\r\n")

            result = pool.convert_file_line_endings(src_file2, dst_file2)
            self.assertTrue(result)
            self.assertEqual(dst_file2.read_bytes(), b"sync test\n")

            # Test 3: Pool asynchronous processing
            src_file3 = self.temp_path / "async.txt"
            dst_file3 = self.temp_path / "async_out.txt"
            src_file3.write_bytes(b"async test\r\n")

            future = pool.convert_file_line_endings_async(src_file3, dst_file3)
            result = future.result(timeout=5.0)
            self.assertTrue(result)
            self.assertEqual(dst_file3.read_bytes(), b"async test\n")

            # Test 4: Binary file handling (no conversion)
            bin_file = self.temp_path / "binary.bin"
            bin_out = self.temp_path / "binary_out.bin"
            binary_content = (
                b"\x00\x01\x02\r\n\x03\x04"  # Contains \r\n but should not convert
            )
            bin_file.write_bytes(binary_content)

            result = _line_ending_worker(str(bin_file), str(bin_out))
            self.assertTrue(result)  # File created
            self.assertEqual(bin_out.read_bytes(), binary_content)  # Unchanged

            # Test 5: Error handling
            nonexistent = self.temp_path / "nonexistent.txt"
            error_out = self.temp_path / "error_out.txt"

            result = _line_ending_worker(str(nonexistent), str(error_out))
            self.assertIsInstance(result, FileNotFoundError)

            # Test 6: Multiple concurrent files
            futures = []
            for i in range(3):
                src = self.temp_path / f"concurrent_{i}.txt"
                dst = self.temp_path / f"concurrent_out_{i}.txt"
                src.write_bytes(f"file {i}\r\n".encode())
                future = pool.convert_file_line_endings_async(src, dst)
                futures.append((future, dst, i))

            # Wait for all and verify
            for future, dst, i in futures:
                result = future.result(timeout=5.0)
                self.assertTrue(result)
                self.assertEqual(dst.read_bytes(), f"file {i}\n".encode())

        finally:
            pool.shutdown()

    def test_global_pool_behavior(self):
        """Test global pool singleton and lifecycle behavior."""
        # Ensure clean state
        shutdown_global_pool()

        # Test singleton behavior
        pool1 = get_line_ending_pool()
        pool2 = get_line_ending_pool()
        self.assertIs(pool1, pool2)

        # Test functional usage
        src_file = self.temp_path / "global_test.txt"
        dst_file = self.temp_path / "global_out.txt"
        src_file.write_bytes(b"global test\r\n")

        result = pool1.convert_file_line_endings(src_file, dst_file)
        self.assertTrue(result)
        self.assertEqual(dst_file.read_bytes(), b"global test\n")

        # Test shutdown and recreation
        shutdown_global_pool()
        pool3 = get_line_ending_pool()
        self.assertIsNot(pool1, pool3)  # New instance created

        # Clean up
        shutdown_global_pool()

    def test_no_changes_suppresses_recompilation(self):
        """Test that when no workers return True, recompilation should be suppressed."""
        pool = LineEndingProcessPool(max_workers=2)

        try:
            # Create identical source and destination files
            src_file = self.temp_path / "unchanged.txt"
            dst_file = self.temp_path / "unchanged_out.txt"

            # Both files have same Unix line endings (no change needed)
            content = b"line1\nline2\nline3\n"
            src_file.write_bytes(content)
            dst_file.write_bytes(content)  # Exact same content

            # Test worker function directly - should return False (no change needed)
            result = _line_ending_worker(str(src_file), str(dst_file))
            self.assertFalse(result)  # Should be False = no change needed

            # Test with pool - should also return False
            result = pool.convert_file_line_endings(src_file, dst_file)
            self.assertFalse(result)  # Should be False = no change needed

            # Multiple identical files should all return False
            results = []
            for i in range(3):
                src = self.temp_path / f"unchanged_{i}.txt"
                dst = self.temp_path / f"unchanged_out_{i}.txt"
                # Create identical files
                src.write_bytes(content)
                dst.write_bytes(content)
                result = pool.convert_file_line_endings(src, dst)
                results.append(result)

            # All should return False (no changes needed)
            self.assertTrue(all(result is False for result in results))

            # This behavior ensures that sync_fastled will return an empty changed_files list,
            # which in turn ensures that compiler.py will skip recompilation when
            # files_will_change is empty and no libraries are missing

        finally:
            pool.shutdown()

    def test_timestamp_aware_change_detection(self):
        """Test that newer source files are always updated, even with identical content.
        
        This is critical for build flags change detection, where timestamps matter
        for downstream build system integration.
        """
        import time
        
        pool = LineEndingProcessPool(max_workers=2)

        try:
            # Create source and destination files with identical content
            src_file = self.temp_path / "timestamp_test.txt"
            dst_file = self.temp_path / "timestamp_test_out.txt"

            # Unix line endings (same after normalization)
            content = b"line1\nline2\nline3\n"
            
            # Create destination file first (older)
            dst_file.write_bytes(content)
            old_dst_mtime = dst_file.stat().st_mtime
            
            # Wait a bit to ensure timestamp difference
            time.sleep(0.1)
            
            # Create source file (newer) with same content
            src_file.write_bytes(content)
            src_mtime = src_file.stat().st_mtime
            
            # Verify source is newer
            self.assertGreater(src_mtime, old_dst_mtime)
            
            # Test that worker updates the file despite identical content
            result = _line_ending_worker(str(src_file), str(dst_file))
            self.assertTrue(result)  # Should return True (file updated)
            
            # Verify destination timestamp was updated
            new_dst_mtime = dst_file.stat().st_mtime
            self.assertGreater(new_dst_mtime, old_dst_mtime)
            
            # Content should remain the same
            self.assertEqual(dst_file.read_bytes(), content)
            
            # Test with pool interface as well
            time.sleep(0.1)
            src_file.write_bytes(content)  # Touch source again
            
            result = pool.convert_file_line_endings(src_file, dst_file)
            self.assertTrue(result)  # Should return True (file updated)
            
            # Test with line ending conversion scenario
            time.sleep(0.1)
            windows_content = b"line1\r\nline2\r\nline3\r\n"
            src_file.write_bytes(windows_content)  # Source has Windows line endings
            # Destination still has Unix line endings from before
            
            result = pool.convert_file_line_endings(src_file, dst_file)
            self.assertTrue(result)  # Should return True (file updated for timestamp)
            
            # Content should be normalized to Unix line endings
            self.assertEqual(dst_file.read_bytes(), content)

        finally:
            pool.shutdown()


if __name__ == "__main__":
    unittest.main()
