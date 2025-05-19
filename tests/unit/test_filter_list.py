"""
Unit test file.
"""

import unittest
from pathlib import Path

from fastled_wasm_compiler.sync import (
    FilterList,
    FilterOp,
    FilterType,
)

_FILTER_LIST = FilterList(
    file_glob=["*.h", "*.cpp", "*.hpp", "*.c", "*.cc", "*.ino"],
    filter_list=[
        FilterOp(
            filter=FilterType.INCLUDE,
            glob=["**/include/**"],
        ),
        FilterOp(
            filter=FilterType.EXCLUDE,
            glob=["**/exclude/**"],
        ),
    ],
)


class FilterListTester(unittest.TestCase):
    """Main tester class."""

    def test_glob(self) -> None:
        """Test command line interface (CLI)."""
        # Define the glob pattern and the directory to search
        expected_included = "include/wasm/wasm.h"
        expected_excluded = "exclude/wasm/wasm.h"

        was_included = _FILTER_LIST.passes(Path(expected_included))
        was_excluded = _FILTER_LIST.passes(Path(expected_excluded))

        self.assertTrue(was_included, f"Expected {expected_included} to be included")
        self.assertFalse(was_excluded, f"Expected {expected_excluded} to be excluded")

    def test_file_level_inclusion(self) -> None:
        """Test file level inclusion."""
        # Define the glob pattern and the directory to search

        exclude_op = FilterOp(
            filter=FilterType.EXCLUDE,
            glob=["**/dir/**/**"],
        )
        include_op = FilterOp(
            filter=FilterType.INCLUDE,
            glob=["**/dir/*.*"],
        )

        # Test inclusion
        included_file = Path("dir/file.h")
        excluded_file = Path("dir/dir2/file.cpp")

        filter_list = FilterList(
            file_glob=["*.h", "*.cpp", "*.hpp", "*.c", "*.cc", "*.ino"],
            filter_list=[exclude_op, include_op],
        )

        was_included = filter_list.passes(included_file)
        was_excluded = filter_list.passes(excluded_file)

        self.assertTrue(was_included, f"Expected {included_file} to be included")
        self.assertFalse(was_excluded, f"Expected {excluded_file} to be excluded")


if __name__ == "__main__":
    unittest.main()
