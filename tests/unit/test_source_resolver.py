"""
Unit test file.
"""

import logging
import unittest
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import (
    dwarf_path_to_file_path,
)
from fastled_wasm_compiler.dwarf_path_to_file_path import logger as dwarf_logger
from fastled_wasm_compiler.dwarf_path_to_file_path import (
    prune_paths,
)
from fastled_wasm_compiler.paths import FASTLED_SRC

# Set debug logging for the path resolution module
dwarf_logger.setLevel(logging.DEBUG)
# Add a handler if there isn't one already
if not dwarf_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
    dwarf_logger.addHandler(handler)

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

    def check_path(self, path: str, expected: str) -> None:
        """Check the path."""
        out = dwarf_path_to_file_path(path)
        self.assertIsInstance(
            out, Path, f"Expected Path, got {type(out)}, which is {out}"
        )
        self.assertEqual(
            out,
            Path(expected),
        )

    def test_fastled_patterns(self) -> None:
        """Test command line interface (CLI)."""
        self.check_path(
            f"fastledsource/js/src/fastledsource/{FASTLED_SRC_STR_RELATIVE}/FastLED.h",
            f"/{FASTLED_SRC_STR_RELATIVE}/FastLED.h",
        )

        self.check_path(
            "/dwarfsource/js/dwarfsource/git/fastled/src/pixel_iterator.h",
            f"/{FASTLED_SRC_STR_RELATIVE}/pixel_iterator.h",
        )

        self.check_path(
            f"dwarfsource/js/sketchsource/{FASTLED_SRC_STR_RELATIVE}/FastLED.h",
            f"/{FASTLED_SRC_STR_RELATIVE}/FastLED.h",
        )

        # self.check_path(
        #     "sketchsource/js/src/direct.h",
        #     "/js/src/direct.h",
        # )


if __name__ == "__main__":
    unittest.main()
