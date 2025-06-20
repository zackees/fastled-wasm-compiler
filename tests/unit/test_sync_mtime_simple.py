"""
Simple unit test for mtime cache optimization that doesn't require external dependencies.
"""

import shutil
import tempfile
import time
import unittest
from pathlib import Path

from fastled_wasm_compiler.sync import (
    _task_copy, 
    clear_file_mtime_cache, 
    _FILE_MTIME_CACHE,
    _should_check_file_content,
    _update_file_mtime_cache
)


class SimpleMtimeCacheTest(unittest.TestCase):
    """Test the mtime cache optimization functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.src_dir = self.temp_dir / "src"
        self.dst_dir = self.temp_dir / "dst" 
        self.src_dir.mkdir()
        self.dst_dir.mkdir()
        clear_file_mtime_cache()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        clear_file_mtime_cache()
    
    def test_mtime_cache_basic_functionality(self):
        """Test basic mtime cache functionality."""
        # Create test files
        src_file = self.src_dir / "test.txt"
        dst_file = self.dst_dir / "test.txt"
        
        src_file.write_text("Hello, World!")
        
        # First copy - should create new file
        result1 = _task_copy(src_file, dst_file, dryrun=False)
        self.assertEqual(result1, dst_file, "First copy should return dst file")
        self.assertTrue(dst_file.exists(), "Destination file should exist")
        self.assertEqual(dst_file.read_text(), "Hello, World!", "Content should match")
        
        # Cache should be empty initially (file didn't exist)
        cache_size = len(_FILE_MTIME_CACHE)
        
        # Second copy - should check content and update cache
        result2 = _task_copy(src_file, dst_file, dryrun=False)
        self.assertIsNone(result2, "Second copy should return None (no changes)")
        
        # Cache should now contain an entry
        self.assertGreater(len(_FILE_MTIME_CACHE), cache_size, "Cache should be populated")
        
        # Third copy - should use cache
        result3 = _task_copy(src_file, dst_file, dryrun=False)
        self.assertIsNone(result3, "Third copy should return None (using cache)")
        
    def test_mtime_cache_detects_changes(self):
        """Test that mtime cache properly detects file changes."""
        src_file = self.src_dir / "test.txt"
        dst_file = self.dst_dir / "test.txt"
        
        # Create initial files
        src_file.write_text("Version 1")
        dst_file.write_text("Version 1")
        
        # First check - should populate cache
        should_check = _should_check_file_content(src_file, dst_file)
        self.assertTrue(should_check, "Should check content on first run")
        
        # Update cache manually to simulate successful comparison
        _update_file_mtime_cache(src_file, dst_file, files_are_equal=True)
        
        # Second check - should use cache
        should_check = _should_check_file_content(src_file, dst_file)
        self.assertFalse(should_check, "Should use cache when files haven't changed")
        
        # Modify source file
        time.sleep(0.1)  # Ensure different mtime
        src_file.write_text("Version 2")
        
        # Third check - should detect change
        should_check = _should_check_file_content(src_file, dst_file)
        self.assertTrue(should_check, "Should detect file change")
        
    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        src_file = self.src_dir / "test.txt"
        dst_file = self.dst_dir / "test.txt"
        
        src_file.write_text("Test content")
        dst_file.write_text("Test content")
        
        # Populate cache
        _update_file_mtime_cache(src_file, dst_file, files_are_equal=True)
        self.assertGreater(len(_FILE_MTIME_CACHE), 0, "Cache should have entries")
        
        # Clear cache
        clear_file_mtime_cache()
        self.assertEqual(len(_FILE_MTIME_CACHE), 0, "Cache should be empty after clearing")
        
    def test_file_modification_detection(self):
        """Test end-to-end file modification detection with cache."""
        src_file = self.src_dir / "test.txt"
        dst_file = self.dst_dir / "test.txt"
        
        # Create initial identical content
        src_file.write_text("Initial content")
        dst_file.write_text("Initial content")
        
        # First _task_copy - should detect no changes and populate cache
        result1 = _task_copy(src_file, dst_file, dryrun=False)
        self.assertIsNone(result1, "Should detect no changes")
        
        # Second _task_copy - should use cache
        result2 = _task_copy(src_file, dst_file, dryrun=False)
        self.assertIsNone(result2, "Should use cache and detect no changes")
        
        # Modify source file
        time.sleep(0.1)  # Ensure different mtime
        src_file.write_text("Modified content")
        
        # Third _task_copy - should detect change despite cache
        result3 = _task_copy(src_file, dst_file, dryrun=False)
        self.assertEqual(result3, dst_file, "Should detect change and return dst file")
        self.assertEqual(dst_file.read_text(), "Modified content", "Content should be updated")


if __name__ == "__main__":
    unittest.main()