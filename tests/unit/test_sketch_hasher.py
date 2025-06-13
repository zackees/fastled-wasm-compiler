"""
Unit test file.
"""

import os
import platform
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastled_wasm_compiler.sketch_hasher import generate_hash_of_project_files

HERE = Path(__file__).parent
TEST_DATA = HERE / "test_data"
SKETCH_CACHE = TEST_DATA / "sketch_cache"

# Check if we're running on macOS
_IS_MACOS = platform.system() == "Darwin"


class SketchHasherTester(unittest.TestCase):
    """Main tester class."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the test class."""
        # Ensure the sketch cache directory exists
        os.environ["TESTING_VERBOSE"] = "1"

    def test_sanity(self) -> None:
        """Test command line interface (CLI)."""
        self.assertTrue(SKETCH_CACHE.exists(), "Sketch cache directory does not exist.")
        self.assertTrue(SKETCH_CACHE.is_dir(), "Sketch cache path is not a directory.")

    @unittest.skipIf(_IS_MACOS, "Skipping test on macOS")
    def test_sketch_hash(self) -> None:
        # copy to a temporary directory

        files: list[str] = [
            "sketch.ino",
            "curr.h",
            "old.h",
        ]

        with TemporaryDirectory() as tmpdir:
            # copy all files to the temporary directory from sketch_cache
            tmp_path = Path(tmpdir)
            for file_str in files:
                file_path = SKETCH_CACHE / file_str
                self.assertTrue(
                    file_path.exists(),
                    f"File {file_str} does not exist in sketch cache.",
                )
                shutil.copy(file_path, tmp_path)

            original_hash = generate_hash_of_project_files(tmp_path)
            print(f"Original hash: {original_hash}")
            # now open up the sketch.ino file and change #include "old.h" -> #include "curr.h"
            sketch_file = tmp_path / "sketch.ino"
            with sketch_file.open("r") as f:
                content = f.read()
            content = content.replace('#include "old.h"', '#include "curr.h"')
            with sketch_file.open("w") as f:
                f.write(content)

            # generate the hash again
            new_hash = generate_hash_of_project_files(tmp_path)

            print(f"New hash: {new_hash}")
            self.assertNotEqual(
                original_hash,
                new_hash,
                "Hash should change after modifying the sketch.",
            )
            print("Test completed successfully, hashes are different as expected.")


if __name__ == "__main__":
    unittest.main()
