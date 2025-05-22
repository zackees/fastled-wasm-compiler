"""
Unit test file.
"""

import unittest
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import (
    dwarf_path_to_file_path,
)
from fastled_wasm_compiler.paths import FASTLED_SRC

FASTLED_SRC_STR_RELATIVE = FASTLED_SRC.as_posix().lstrip("/")


class SourceFileResolver(unittest.TestCase):
    """Main tester class."""

    def test_fastled_patterns(self) -> None:
        """Test command line interface (CLI)."""

        # path = (
        #     f"FastLED/FastLED.h"
        # )
        # out = prune_paths(path)
        # self.assertIsInstance(out, str)
        # self.assertEqual(
        #     out,
        #     "/git/fastled/src/FastLED.h",
        # )

        # path = "stdlib/__stddef_max_align_t.h"
        # out = prune_paths(path)
        # self.assertIsInstance(out, str)
        # self.assertEqual(
        #     out,
        #     "/emsdk/upstream/lib/clang/21/include/__stddef_max_align_t.h",
        # )

        out = dwarf_path_to_file_path(
            "FastLED/FastLED.h",
            check_exists=False,
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path("/git/fastled/src/FastLED.h"),
        )

        out = dwarf_path_to_file_path(
            "stdlib/vector",
            check_exists=False,
        )
        self.assertEqual(
            out,
            Path("/emsdk/emscripten/cache/sysroot/include/vector"),
        )

        out = dwarf_path_to_file_path(
            "Sketch/Sketch.ino",
            check_exists=False,
        )
        self.assertIsInstance(out, Path)
        self.assertEqual(
            out,
            Path("/js/src/Sketch.ino"),
        )


if __name__ == "__main__":
    unittest.main()
