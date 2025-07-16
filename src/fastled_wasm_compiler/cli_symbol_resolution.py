"""
CLI module to test symbol resolution functionality.

This demonstrates how DWARF debug paths are resolved to actual file paths.
"""

import sys
from pathlib import Path

from fastled_wasm_compiler.dwarf_path_to_file_path import dwarf_path_to_file_path


def main() -> int:
    """Test symbol resolution and exit with appropriate code."""
    print("=== FastLED WASM Symbol Resolution Test ===")
    
    # Test case: dwarfsource/js/src/test.h should resolve to js/src/test.h
    test_input = "dwarfsource/js/src/test.h"
    expected_output = "js/src/test.h"
    
    print(f"\nTesting symbol resolution:")
    print(f"Input:    {test_input}")
    print(f"Expected: {expected_output}")
    
    # Call dwarf_path_to_file_path with check_exists=False as requested
    result = dwarf_path_to_file_path(test_input, check_exists=False)
    
    if isinstance(result, Exception):
        print(f"❌ Resolution failed: {result}")
        return 1
    
    resolved_path = str(result)
    print(f"Resolved: {resolved_path}")
    
    # Check if the resolution matches expected output
    # Handle both absolute and relative path formats
    if resolved_path == expected_output or resolved_path == f"/{expected_output}":
        print("✅ Symbol resolution test PASSED")
        return 0
    else:
        print(f"❌ Symbol resolution test FAILED")
        print(f"   Expected: {expected_output}")
        print(f"   Got:      {resolved_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 