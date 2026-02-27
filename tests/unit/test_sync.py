"""
Unit test file.
"""

import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import httpx

from fastled_wasm_compiler.sync import ALLOWED_EXTENSIONS, sync_fastled

HERE = Path(__file__).parent
SYNC_DATA = HERE / ".sync_data"
SYNC_DATA_SRC = SYNC_DATA / "src"
SYNC_DATA_DST = SYNC_DATA / "dst"

# Cache downloaded file to speed up repeated test runs
CACHE_DIR = Path.cwd() / ".cache" / "test-fastled-downloads"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://github.com/FastLED/FastLED/archive/refs/heads/master.zip"


def _get_first_directory(src: Path) -> Path:
    """Get the first directory in the sync data source."""
    for item in src.iterdir():
        if item.is_dir():
            return item
    raise FileNotFoundError("No directories found in sync data source.")


class ExtensionFilteringTester(unittest.TestCase):
    """Test class for extension-based file filtering functionality."""

    def setUp(self) -> None:
        """Check if Unix find command is available (not on Windows).

        Note: The sync code automatically uses Python fallback on Windows because
        Git Bash's find command has issues with Windows paths and complex expressions.
        On Unix-like systems, we check if find is available and skip if it's not,
        though the Python fallback would be used automatically in that case.
        """
        import shutil
        import sys

        # On Windows, we always use Python fallback, so find command isn't needed
        if sys.platform == "win32":
            return

        # On Unix-like systems, check if find is available
        find_cmd = shutil.which("find")
        if not find_cmd:
            self.skipTest(
                "Unix find command not available - file sync will use Python fallback"
            )

    def test_extension_filtering(self) -> None:
        """Test that only files with allowed extensions are synced and unsuffixed files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "test_src"
            dst_dir = Path(tmpdir) / "test_dst"
            src_dir.mkdir()

            # Create directory structure for platforms testing
            (src_dir / "platforms").mkdir()
            (src_dir / "platforms" / "shared").mkdir()
            (src_dir / "platforms" / "wasm").mkdir()
            (src_dir / "platforms" / "stub").mkdir()
            (src_dir / "platforms" / "arduino").mkdir()  # Included (unity build)
            (src_dir / "platforms" / "esp32").mkdir()  # Included (unity build)
            (src_dir / "platforms" / "unknown").mkdir()  # Included (unity build)

            # Create files with allowed extensions (should be synced)
            allowed_files = {
                # Regular source files
                "main.cpp": "int main() { return 0; }",
                "header.h": "#pragma once",
                "another.hpp": "#include <iostream>",
                "config.ini": "[section]\nkey=value",
                "script.js": "console.log('hello');",
                "module.mjs": "export default {};",
                "types.ts": "// TypeScript definitions",
                "page.html": "<html><body></body></html>",
                "style.css": "body { margin: 0; }",
                "readme.txt": "This is a readme file",
                "source.c": "#include <stdio.h>",
                "alt.cc": "// C++ code",
                "extended.cxx": "// Another C++ file",
                "plus.c++": "// C++ with plus extension",
                "alt_header.hh": "// Alternative header",
                "extended_header.hxx": "// Extended header",
                "plus_header.h++": "// Header with plus",
                # Files directly in platforms/ (should be included)
                "platforms/platform_config.h": "#define PLATFORM_CONFIG",
                "platforms/common.cpp": "// Common platform code",
                # Files in allowed platform subdirectories (should be included)
                "platforms/shared/shared_utils.h": "#pragma once // shared",
                "platforms/shared/shared_impl.cpp": "// shared implementation",
                "platforms/wasm/wasm_specific.h": "#pragma once // wasm",
                "platforms/wasm/wasm_impl.cpp": "// wasm implementation",
                "platforms/stub/stub_header.h": "#pragma once // stub",
                "platforms/stub/stub_impl.cpp": "// stub implementation",
                # Unity build now includes all platform subdirectories
                "platforms/arduino/arduino_code.cpp": "// Arduino specific code",
                "platforms/arduino/arduino_header.h": "#pragma once // arduino",
                "platforms/esp32/esp32_code.cpp": "// ESP32 specific code",
                "platforms/esp32/esp32_header.h": "#pragma once // esp32",
                "platforms/unknown/unknown_code.cpp": "// Unknown platform code",
            }

            # Create files that should be excluded (no extension or disallowed extensions)
            excluded_files = {
                # Files without proper extensions
                "unsuffixed_file": "This file has no extension",
                "readme": "This readme has no extension",
                "_readme": "This _readme has no extension",
                "Makefile": "# This is a Makefile",
                "LICENSE": "MIT License text",
                "image.png": b"fake png data",
                "photo.jpg": b"fake jpg data",
                "animation.gif": b"fake gif data",
                "documentation.md": "# Markdown documentation",
                "script.py": "print('Python script')",
                "archive.zip": b"fake zip data",
                "executable": "#!/bin/bash\necho hello",
                "config.yaml": "key: value",
                "data.json": '{"key": "value"}',
                "backup.bak": "backup file",
                "temp.tmp": "temporary file",
                "log.log": "log entries",
                "example.disabled": "disabled file",
            }

            # Write allowed files to source directory
            for filename, content in allowed_files.items():
                file_path = src_dir / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, str):
                    file_path.write_text(content)
                else:
                    file_path.write_bytes(content)

            # Write excluded files to source directory
            for filename, content in excluded_files.items():
                file_path = src_dir / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, str):
                    file_path.write_text(content)
                else:
                    file_path.write_bytes(content)

            # Verify all test files were created
            all_src_files = list(src_dir.rglob("*"))
            all_src_file_count = len([f for f in all_src_files if f.is_file()])
            expected_total = len(allowed_files) + len(excluded_files)
            self.assertEqual(
                all_src_file_count,
                expected_total,
                f"Expected {expected_total} files, got {all_src_file_count}",
            )

            # Perform sync
            sync_result = sync_fastled(
                src_dir, dst_dir, dryrun=False, sync_examples=False
            )

            # Verify sync completed successfully
            from fastled_wasm_compiler.sync import SyncResult

            self.assertIsInstance(sync_result, SyncResult)
            self.assertEqual(len(sync_result.all_changed_files), len(allowed_files))

            # Check that all allowed files were copied
            dst_files = {
                f.relative_to(dst_dir).as_posix()
                for f in dst_dir.rglob("*")
                if f.is_file()
            }

            for allowed_file in allowed_files.keys():
                self.assertIn(
                    allowed_file,
                    dst_files,
                    f"Allowed file '{allowed_file}' should have been synced",
                )

                # Verify file content was copied correctly
                src_content = (src_dir / allowed_file).read_text(errors="ignore")
                dst_content = (dst_dir / allowed_file).read_text(errors="ignore")
                self.assertEqual(
                    src_content,
                    dst_content,
                    f"Content mismatch for file '{allowed_file}'",
                )

            # Check that excluded files were NOT copied
            for excluded_file in excluded_files.keys():
                self.assertNotIn(
                    excluded_file,
                    dst_files,
                    f"Excluded file '{excluded_file}' should NOT have been synced",
                )

            # Verify exact count
            self.assertEqual(
                len(dst_files),
                len(allowed_files),
                f"Expected exactly {len(allowed_files)} files in destination, got {len(dst_files)}: {dst_files}",
            )

            # Verify platforms filtering specifically
            platform_files_in_dst = [f for f in dst_files if f.startswith("platforms/")]

            print("✅ Extension and platforms filtering test passed:")
            print(
                f"   - {len(allowed_files)} files with allowed extensions were synced"
            )
            print(
                f"   - {len(excluded_files)} files without proper extensions were excluded"
            )
            print(
                f"   - {len(platform_files_in_dst)} platform files synced: {platform_files_in_dst}"
            )
            print("   - All platform subdirectories now included (unity build)")
            print(f"   - Allowed extensions: {ALLOWED_EXTENSIONS}")


class SyncTester(unittest.TestCase):
    """Main tester class."""

    def setUp(self):
        """Set up test environment."""
        # Skip if integration tests not enabled (this downloads large files)
        if not os.environ.get("RUN_INTEGRATION_TESTS"):
            self.skipTest("Integration tests not enabled. Set RUN_INTEGRATION_TESTS=1")

    def test_glob(self) -> None:
        """Test command line interface (CLI)."""
        # Define the glob pattern and the directory to search
        SYNC_DATA_SRC.mkdir(parents=True, exist_ok=True)
        # SYNC_DATA_DST.mkdir(parents=True, exist_ok=True)

        # Use cached download to speed up repeated test runs
        cached_zip = CACHE_DIR / "fastled-master.zip"
        src_zip = SYNC_DATA_SRC / "master.zip"

        if not cached_zip.exists():
            print("Downloading FastLED repository (cached for future runs)...")
            response = httpx.get(URL, follow_redirects=True)
            content = response.content
            assert len(content) >= 10000, "Downloaded file is too small"
            with open(cached_zip, "wb") as f:
                f.write(content)
            print(f"Downloaded and cached: {cached_zip}")
        else:
            print(f"Using cached download: {cached_zip}")

        # Copy from cache to test location
        shutil.copy2(cached_zip, src_zip)

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
        # Unity build includes all platform directories
        # arm directory should now be synced if present in source
        self.assertTrue(
            (
                SYNC_DATA_DST / "fastled" / "src" / "platforms" / "assert_defs.h"
            ).exists(),
            "Expected assert_defs.h file",
        )
        # assert (SYNC_DATA_DST / "fastled" / "examples" / "Blink" / "Blink.ino").exists(), "Expected Blink.ino file"


if __name__ == "__main__":
    unittest.main()
