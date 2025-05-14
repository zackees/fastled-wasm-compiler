"""
Unit test file.
"""

import unittest
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import dwarf_path_to_file_path


class SourceFileResolver(unittest.TestCase):
    """Main tester class."""

    def test_fastled_patterns(self) -> None:
        """Test command line interface (CLI)."""

        out: Path | Exception = dwarf_path_to_file_path(
            "fastledsource/js/src/fastledsource/git/fastled/src/FastLED.h",
            check_exists=False,
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path("/git/fastled/src/FastLED.h"),
        )

        out = dwarf_path_to_file_path(
            "sketchsource/js/sketchsource/headers/FastLED.h", check_exists=False
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path("/headers/FastLED.h"),
        )
        out = dwarf_path_to_file_path(
            "sketchsource/js/src/direct.h", check_exists=False
        )
        self.assertIsInstance(out, str)
        self.assertEqual(
            out,
            Path("/js/src/direct.h"),
        )


if __name__ == "__main__":
    unittest.main()
