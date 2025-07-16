"""
CLI module to test symbol resolution functionality.

This demonstrates how DWARF debug paths are resolved to actual file paths.
"""

import sys

from fastled_wasm_compiler.dwarf_path_to_file_path import dwarf_path_to_file_path


def main() -> int:
    """Test symbol resolution and exit with appropriate code."""
    print("=== FastLED WASM Symbol Resolution Test ===")

    # Test case: dwarfsource/js/src/test.h should resolve to js/src/test.h
    test_input = "dwarfsource/js/src/test.h"
    expected_output = "js/src/test.h"

    print("\nTesting symbol resolution:")
    print(f"Input:    {test_input}")
    print(f"Expected: {expected_output}")

    # Call dwarf_path_to_file_path with check_exists=False as requested
    result = dwarf_path_to_file_path(test_input, check_exists=False)

    if isinstance(result, Exception):
        print(f"❌ Resolution failed: {result}")
        return 1

    resolved_path = str(result)
    print(f"Resolved: {resolved_path}")

    # Normalize path separators for cross-platform compatibility
    normalized_path = resolved_path.replace("\\", "/")

    # Ensure we have a leading slash for the expected format
    final_path = (
        normalized_path if normalized_path.startswith("/") else f"/{normalized_path}"
    )
    print(f"Final resolved path: {final_path}")

    # Check if the resolution matches expected output
    # Handle both absolute and relative path formats
    if normalized_path == expected_output or normalized_path == f"/{expected_output}":
        print("✅ Symbol resolution test PASSED")
        return 0
    else:
        print("❌ Symbol resolution test FAILED")
        print(f"   Expected: {expected_output}")
        print(f"   Got:      {normalized_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
