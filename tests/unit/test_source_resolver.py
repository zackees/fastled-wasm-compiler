"""
Unit test file.
"""

import unittest
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import (
    dwarf_path_to_file_path,
    prune_paths,
)
from fastled_wasm_compiler.paths import FASTLED_SRC

FASTLED_SRC_STR_RELATIVE = FASTLED_SRC.as_posix().lstrip("/")


class SourceFileResolver(unittest.TestCase):
    """Main tester class."""

    def test_prune_paths(self) -> None:
        """Test the path pruning function."""

        path = (
            f"fastledsource/js/src/fastledsource/{FASTLED_SRC_STR_RELATIVE}/FastLED.h"
        )
        out = prune_paths(path)
        self.assertIsInstance(out, str)
        self.assertEqual(
            out,
            "git/fastled/src/FastLED.h",
        )

        path = "sketchsource/js/sketchsource/emsdk/upstream/lib/clang/21/include/__stddef_max_align_t.h"
        out = prune_paths(path)
        self.assertIsInstance(out, str)
        self.assertEqual(
            out,
            "emsdk/upstream/lib/clang/21/include/__stddef_max_align_t.h",
        )

    def test_fastled_patterns(self) -> None:
        """Test command line interface (CLI)."""

        out: Path | Exception = dwarf_path_to_file_path(
            f"fastledsource/js/src/fastledsource/{FASTLED_SRC_STR_RELATIVE}/FastLED.h",
            check_exists=False,
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path(f"/{FASTLED_SRC_STR_RELATIVE}/FastLED.h"),
        )

        out = dwarf_path_to_file_path(
            f"sketchsource/js/sketchsource/{FASTLED_SRC_STR_RELATIVE}/FastLED.h",
            check_exists=False,
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path(f"/{FASTLED_SRC_STR_RELATIVE}/FastLED.h"),
        )
        out = dwarf_path_to_file_path(
            "sketchsource/js/src/direct.h", check_exists=False
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path("/js/src/direct.h"),
        )


if __name__ == "__main__":
    unittest.main()
