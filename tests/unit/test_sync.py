"""
Unit test file.
"""

import shutil
import unittest
import zipfile
from pathlib import Path

import httpx

from fastled_wasm_compiler.sync import sync_fastled

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


if __name__ == "__main__":
    unittest.main()
