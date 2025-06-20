"""
Unit test file.
"""

import shutil
import time
import unittest
import zipfile
from pathlib import Path

import httpx

from fastled_wasm_compiler.sync import sync_fastled, clear_file_mtime_cache, _FILE_MTIME_CACHE

HERE = Path(__file__).parent
SYNC_DATA = HERE / ".sync_data"
SYNC_DATA_SRC = SYNC_DATA / "src"
SYNC_DATA_DST = SYNC_DATA / "dst"

URL = "https://github.com/FastLED/FastLED/archive/refs/heads/master.zip"


def _get_first_directory(src: Path) -> Path:
    """Get the first directory in the sync data source."""
    for item in src.iterdir():
        if item.is_dir():
            return item
    raise FileNotFoundError("No directories found in sync data source.")


class SyncTester(unittest.TestCase):
    """Main tester class."""

    def test_glob(self) -> None:
        """Test command line interface (CLI)."""
        # Define the glob pattern and the directory to search
        SYNC_DATA_SRC.mkdir(parents=True, exist_ok=True)
        # SYNC_DATA_DST.mkdir(parents=True, exist_ok=True)

        src_zip = SYNC_DATA_SRC / "master.zip"
        if not src_zip.exists():
            response = httpx.get(URL, follow_redirects=True)
            content = response.content
            assert len(content) >= 10000, "Downloaded file is too small"
            with open(src_zip, "wb") as f:
                f.write(content)
            f.close()
        # unzip the file
        # assert that the file exists
        assert (SYNC_DATA_SRC / "master.zip").exists(), "File not found"
        with zipfile.ZipFile(SYNC_DATA_SRC / "master.zip", "r") as zip_ref:
            zip_ref.extractall(SYNC_DATA_SRC)

        first_dir = _get_first_directory(SYNC_DATA_SRC)
        print(f"first_dir: {first_dir}")
        assert first_dir.is_dir(), f"Expected {first_dir.absolute()} to be a directory"
        assert (first_dir / "src").exists(), "Expected FastLED-master directory"
        assert (first_dir / "src" / "FastLED.h").exists(), "Expected FastLED.h file"

        shutil.rmtree(SYNC_DATA_DST, ignore_errors=True)

        fastled_src = first_dir / "src"
        sync_fastled(
            fastled_src,
            SYNC_DATA_DST / "fastled" / "src",
        )

        # # now test that sync_fastled copied the files
        self.assertTrue(
            (SYNC_DATA_DST / "fastled" / "src").exists(),
            "Expected fastled/src directory",
        )
        self.assertTrue(
            (SYNC_DATA_DST / "fastled" / "src" / "FastLED.h").exists(),
            "Expected FastLED.h file",
        )
        self.assertTrue(
            (SYNC_DATA_DST / "fastled" / "examples").exists(),
            "Expected fastled/examples directory",
        )
        self.assertTrue(
            (SYNC_DATA_DST / "fastled" / "examples" / "Blink").exists(),
            "Expected fastled/examples/Blink directory",
        )
        self.assertFalse(
            (SYNC_DATA_DST / "fastled" / "src" / "platforms" / "arm").exists(),
            "Expected arm directory to be excluded",
        )
        self.assertTrue(
            (
                SYNC_DATA_DST / "fastled" / "src" / "platforms" / "assert_defs.h"
            ).exists(),
            "Expected assert_defs.h file",
        )
        # assert (SYNC_DATA_DST / "fastled" / "examples" / "Blink" / "Blink.ino").exists(), "Expected Blink.ino file"

    def test_mtime_cache_optimization(self) -> None:
        """Test that the mtime cache optimization works correctly."""
        # Setup test directories
        test_src = SYNC_DATA / "mtime_test_src"
        test_dst = SYNC_DATA / "mtime_test_dst"
        
        # Clean up from any previous runs
        shutil.rmtree(test_src, ignore_errors=True)
        shutil.rmtree(test_dst, ignore_errors=True)
        clear_file_mtime_cache()
        
        # Create test source structure
        test_src.mkdir(parents=True, exist_ok=True)
        (test_src / "FastLED.h").write_text("#ifndef FASTLED_H\n#define FASTLED_H\n// Test FastLED header\n#endif\n")
        (test_src / "test_file.cpp").write_text("#include <FastLED.h>\nint main() { return 0; }\n")
        
        # First sync - should copy files and populate cache
        print("Running first sync...")
        changed_files_1 = sync_fastled(test_src, test_dst / "fastled" / "src", sync_examples=False)
        
        # Verify files were copied
        self.assertTrue((test_dst / "fastled" / "src" / "FastLED.h").exists(), "FastLED.h should be copied")
        self.assertTrue((test_dst / "fastled" / "src" / "test_file.cpp").exists(), "test_file.cpp should be copied")
        self.assertEqual(len(changed_files_1), 2, "Should have copied 2 files")
        
        # Verify cache is populated
        cache_size_after_first_sync = len(_FILE_MTIME_CACHE)
        self.assertGreater(cache_size_after_first_sync, 0, "Cache should be populated after first sync")
        
        # Second sync - should use cache and not change any files
        print("Running second sync (should use cache)...")
        time.sleep(0.1)  # Small delay to ensure different timestamp if needed
        changed_files_2 = sync_fastled(test_src, test_dst / "fastled" / "src", sync_examples=False)
        
        # Should detect no changes due to cache optimization
        self.assertEqual(len(changed_files_2), 0, "Second sync should detect no changes due to cache")
        
        # Verify cache size is consistent
        cache_size_after_second_sync = len(_FILE_MTIME_CACHE)
        self.assertEqual(cache_size_after_first_sync, cache_size_after_second_sync, "Cache size should be consistent")
        
        # Modify a source file to test cache invalidation
        print("Modifying source file...")
        time.sleep(0.1)  # Ensure different mtime
        (test_src / "test_file.cpp").write_text("#include <FastLED.h>\nint main() { printf(\"Hello!\"); return 0; }\n")
        
        # Third sync - should detect the changed file despite cache
        print("Running third sync (should detect change)...")
        changed_files_3 = sync_fastled(test_src, test_dst / "fastled" / "src", sync_examples=False)
        
        # Should detect the modified file
        self.assertEqual(len(changed_files_3), 1, "Third sync should detect 1 changed file")
        self.assertTrue(any("test_file.cpp" in str(f) for f in changed_files_3), "Should detect test_file.cpp as changed")
        
        # Test cache clearing functionality
        print("Testing cache clearing...")
        clear_file_mtime_cache()
        self.assertEqual(len(_FILE_MTIME_CACHE), 0, "Cache should be empty after clearing")
        
        # Fourth sync with cleared cache - should still work correctly
        print("Running fourth sync (with cleared cache)...")
        changed_files_4 = sync_fastled(test_src, test_dst / "fastled" / "src", sync_examples=False)
        
        # Should detect no changes (files are already in sync)
        self.assertEqual(len(changed_files_4), 0, "Fourth sync should detect no changes")
        
        # Verify cache is repopulated
        self.assertGreater(len(_FILE_MTIME_CACHE), 0, "Cache should be repopulated after sync with cleared cache")
        
        # Test explicit cache clearing parameter
        print("Testing explicit cache clearing parameter...")
        changed_files_5 = sync_fastled(test_src, test_dst / "fastled" / "src", sync_examples=False, clear_mtime_cache=True)
        self.assertEqual(len(changed_files_5), 0, "Sync with clear_mtime_cache=True should detect no changes")
        
        print("Mtime cache optimization test completed successfully!")


if __name__ == "__main__":
    unittest.main()
